import axios from 'axios';
import { getApiKeysForUser, getModelPricing, consumeCredits, logGeneration, supabase } from './supabaseService';
import { User, Generation } from '../types';
import { config } from '../config';

const FREEPIK_API_BASE = 'https://api.freepik.com/v1/ai';

// Simplified Model Definitions (Key mapping)
const MODEL_ENDPOINTS: Record<string, any> = {
    'kling-v2-1-std': { endpoint: '/image-to-video/kling-v2-1-std', param: 'duration' },
    'kling-v2-1-pro': { endpoint: '/image-to-video/kling-v2-1-pro', param: 'duration' },
    'kling-v2-5-pro': { endpoint: '/image-to-video/kling-v2-5-pro', param: 'duration' },
    'kling-v2-6-pro': { endpoint: '/image-to-video/kling-v2-6-pro', param: 'duration' },
    'kling-o1-std': { endpoint: '/image-to-video/kling-o1-std', param: 'duration' },
    'wan-v2-6-1080p': { endpoint: '/image-to-video/wan-v2-6-1080p', param: 'duration', requiresHttps: true },
    'minimax-hailuo-02-1080p': { endpoint: '/image-to-video/minimax-hailuo-02-1080p', param: 'duration' },
    'runway-gen4-turbo': { endpoint: '/image-to-video/runway-gen4-turbo', param: 'duration', requiresHttps: true },
    'pixverse-v5-720p': { endpoint: '/image-to-video/pixverse-v5', param: 'duration', requiresHttps: true },
};

const MODEL_STATUS_ENDPOINTS: Record<string, string> = {
    'kling-v2-1-std': '/image-to-video/kling-v2-1',
    'kling-v2-1-pro': '/image-to-video/kling-v2-1',
    'kling-v2-5-pro': '/image-to-video/kling-v2-5-pro',
    'kling-v2-6-pro': '/image-to-video/kling-v2-6',
    'kling-o1-std': '/image-to-video/kling-o1',
    'wan-v2-6-1080p': '/image-to-video/wan-v2-6-1080p',
    'minimax-hailuo-02-1080p': '/image-to-video/minimax-hailuo-02-1080p',
    'runway-gen4-turbo': '/image-to-video/runway-gen4-turbo',
    'pixverse-v5-720p': '/image-to-video/pixverse-v5',
};

export async function processGeneration(user: User, modelName: string, prompt: string, imageUrl: string, options: any = {}) {
    const modelConfig = MODEL_ENDPOINTS[modelName];
    if (!modelConfig) throw new Error('Model not found');

    const pricing = await getModelPricing(modelName);
    const creditCost = pricing?.credit_cost || 1;

    if ((user.monthly_credits + user.extra_credits) < creditCost && user.type !== 'UNLIMITED' && user.type !== 'ADVANCE') {
        throw new Error('Kredit tidak cukup.');
    }

    let payload: any = {
        image: imageUrl,
        prompt: prompt,
    };

    if (modelName.includes('wan')) {
        payload.size = '1280*720';
    }
    if (modelConfig.param === 'duration') {
        payload.duration = String(options.duration || '5');
    }
    if (modelName.includes('pixverse')) {
        payload = {
            image_url: imageUrl,
            prompt: prompt,
            resolution: '720p',
            duration: parseInt(options.duration || '5')
        };
    }
    if (modelName.includes('runway-gen4')) {
        payload.ratio = '1280:720'; // Default ratio
        payload.duration = parseInt(options.duration || '5');
    }

    const keys = await getApiKeysForUser(user);
    if (!keys.length) throw new Error('Bot sedang sibuk (No API Keys).');

    let taskId = '';
    let usedKey = '';

    for (const key of keys) {
        try {
            console.log(`Using Key: ...${key.slice(-4)}`);
            const res = await axios.post(`${FREEPIK_API_BASE}${modelConfig.endpoint}`, payload, {
                headers: {
                    'x-freepik-api-key': key,
                    'Content-Type': 'application/json'
                }
            });

            if (res.data?.data?.task_id) {
                taskId = res.data.data.task_id;
            } else if (res.data?.task_id) {
                taskId = res.data.task_id;
            }

            usedKey = key;
            break;
        } catch (e: any) {
            console.error(`API Fail with key ...${key.slice(-4)}:`, e.response?.data || e.message);
            if ([403, 401, 429, 503].includes(e.response?.status)) {
                continue;
            }
            throw new Error(`Gagal generate: ${e.response?.data?.error || e.message}`);
        }
    }

    if (!taskId) throw new Error('Semua API Key sibuk atau habis kuota.');

    if (user.type !== 'UNLIMITED' && user.type !== 'ADVANCE') {
        await consumeCredits(user.id, creditCost);
    }

    const genRecord = await logGeneration({
        user_id: user.id,
        model_name: modelName,
        prompt: prompt,
        status: 'processing',
        task_id: taskId,
        credits_used: creditCost,
        api_key_used: usedKey,
        thumbnail_url: imageUrl
    });

    return { taskId, generationId: genRecord?.id, usedKey };
}

export async function pollGenerationStatus(taskId: string, modelName: string, apiKey: string): Promise<{ status: string; videoUrl?: string; message?: string }> {
    const statusEndpoint = MODEL_STATUS_ENDPOINTS[modelName] || '/image-to-video/kling-v2-1';

    try {
        const res = await axios.get(`${FREEPIK_API_BASE}${statusEndpoint}/${taskId}`, {
            headers: { 'x-freepik-api-key': apiKey }
        });

        const data = res.data.data || res.data;
        const status = (data.status || '').toUpperCase();

        if (status === 'COMPLETED' || status === 'SUCCESS') {
            const videoUrl = data.generated?.[0] || data.video?.url || data.result?.url;
            return { status: 'completed', videoUrl };
        } else if (status === 'FAILED' || status === 'ERROR') {
            return { status: 'failed', message: data.error || 'Unknown error' };
        }

        return { status: 'processing' };
    } catch (e: any) {
        console.error('Poll Error:', e.response?.data || e.message);
        if (e.response?.status === 404) return { status: 'processing' }; // Not found usually means queueing
        return { status: 'error', message: e.message };
    }
}

export async function finalizeGeneration(generationId: string, videoUrl: string, userId: string, modelName: string) {
    try {
        console.log(`Finalizing generation ${generationId}...`);

        // Dynamic import to avoid circular dependency if any (though r2Service is leaf)
        const { uploadVideoToR2 } = await import('./r2Service');

        // Upload to R2
        let r2Url: string | null = null;
        try {
            r2Url = await uploadVideoToR2(videoUrl, `gen_${generationId}`, userId);
        } catch (r2Err) {
            console.error('Failed to upload execution to R2:', r2Err);
        }

        // Update DB
        const { error } = await supabase.from('generations').update({
            status: 'completed',
            video_url: videoUrl,
            r2_url: r2Url || videoUrl
        }).eq('id', generationId);

        if (error) console.error('DB Update Error:', error);

        // Increment count
        await supabase.rpc('increment_video_count', { user_id: userId });

        return r2Url || videoUrl;
    } catch (e) {
        console.error('Finalize Error:', e);
        return videoUrl;
    }
}

import { createClient } from '@supabase/supabase-js';
import { config } from '../config';
import { User, Generation, ModelPricing } from '../types';

const supabase = createClient(config.supabase.url, config.supabase.serviceRoleKey);

export { supabase };

// ========== SUBSCRIPTION & CREDITS ==========

export async function consumeCredits(userId: string, amount: number = 1): Promise<{
    success: boolean;
    monthly_credits: number;
    extra_credits: number;
    error?: string;
}> {
    const { data: user, error: fetchError } = await supabase
        .from('users')
        .select('monthly_credits, extra_credits')
        .eq('id', userId)
        .single();

    if (fetchError || !user) {
        return { success: false, monthly_credits: 0, extra_credits: 0, error: 'User not found' };
    }

    let { monthly_credits, extra_credits } = user;
    let remaining = amount;

    if (monthly_credits + extra_credits < amount) {
        return { success: false, monthly_credits, extra_credits, error: `Kredit tidak cukup. Butuh ${amount}, saldo: ${monthly_credits + extra_credits}` };
    }

    if (monthly_credits > 0) {
        const deduct = Math.min(monthly_credits, remaining);
        monthly_credits -= deduct;
        remaining -= deduct;
    }

    if (remaining > 0 && extra_credits > 0) {
        const deduct = Math.min(extra_credits, remaining);
        extra_credits -= deduct;
        remaining -= deduct;
    }

    const { error: updateError } = await supabase
        .from('users')
        .update({ monthly_credits, extra_credits })
        .eq('id', userId);

    if (updateError) {
        return { success: false, monthly_credits: 0, extra_credits: 0, error: 'Failed to update credits' };
    }

    return { success: true, monthly_credits, extra_credits };
}

// ========== LOGGING ==========

export async function logGeneration(data: Partial<Generation>): Promise<Generation | null> {
    const { data: result, error } = await supabase
        .from('generations')
        .insert(data)
        .select()
        .single();

    if (error) {
        console.error('Error logging generation:', error);
        return null;
    }
    return result as Generation;
}

// ========== API KEYS ==========

export async function getApiKeysForUser(user: User): Promise<string[]> {
    if (user.type === 'ADVANCE' && user.user_api_key) {
        return [user.user_api_key];
    }

    let apiKeys: string[] = [];
    if (user.group && user.group.api_keys.length > 0) {
        apiKeys = user.group.api_keys;
    } else {
        const { data } = await supabase
            .from('api_groups')
            .select('api_keys')
            .eq('name', 'default')
            .single();
        if (data) apiKeys = data.api_keys;
    }

    return apiKeys.length > 0 ? apiKeys : [];
}

export async function getModelPricing(modelId: string): Promise<ModelPricing | null> {
    const { data, error } = await supabase
        .from('ai_models')
        .select('*')
        .eq('model_id', modelId)
        .eq('is_active', true)
        .single();

    if (error) return null;
    return data as ModelPricing;
}

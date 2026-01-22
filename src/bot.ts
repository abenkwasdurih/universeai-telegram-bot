import { Telegraf, Context, Markup } from 'telegraf';
import axios from 'axios';
import { config } from './config';
import { loginUser, logoutUser, validateSession, takeoverSession } from './auth';
import { processGeneration, pollGenerationStatus, finalizeGeneration } from './services/generationService';
import { uploadImageToStorage } from './services/storageService';

if (!config.botToken) {
    throw new Error('BOT_TOKEN must be provided!');
}

const bot = new Telegraf(config.botToken);

// Simple session state: ChatID -> { imageUrl: string, model: string; step: 'PROMPT' }
const userState = new Map<number, { imageUrl: string; model: string; step: 'PROMPT' }>();

// Available models for selection
const MODEL_KEYBOARD = Markup.inlineKeyboard([
    [Markup.button.callback('Kling 2.1 Standard', 'model_kling-v2-1-std')],
    [Markup.button.callback('Kling 2.5 Pro', 'model_kling-v2-5-pro')],
    [Markup.button.callback('Hailuo 2.1 1080p', 'model_minimax-hailuo-02-1080p')],
    [Markup.button.callback('Runway Gen4', 'model_runway-gen4-turbo')],
]);

bot.use(async (ctx: any, next: () => Promise<void>) => {
    // Log message
    if (ctx.from) {
        console.log(`[${new Date().toISOString()}] ${ctx.from.id}: ${ctx.message && 'text' in ctx.message ? ctx.message.text : 'Action'}`);
    }
    await next();
});

bot.command('start', (ctx: any) => {
    ctx.reply('Selamat datang di UniverseAI Bot! 🤖\n\nSilakan login dengan format:\n/login <kode_akses>\n\nContoh:\n/login UNIVERSE-12345');
});

bot.command('login', async (ctx: any) => {
    const messageText = ctx.message && 'text' in ctx.message ? ctx.message.text : '';
    const args = messageText.split(' ');
    if (args.length !== 2) {
        return ctx.reply('Format salah. Gunakan: /login <kode_akses>');
    }
    const code = args[1];
    const result = await loginUser(code, ctx.from!.id);
    ctx.reply(result.message);
});

bot.command('logout', async (ctx: any) => {
    const result = await logoutUser(ctx.from!.id);
    ctx.reply(result.message);
});

bot.command('takeover', async (ctx: any) => {
    const result = await takeoverSession(ctx.from!.id);
    ctx.reply(result.message);
});

bot.command('status', async (ctx: any) => {
    const { valid, user, message } = await validateSession(ctx.from!.id);
    if (!valid || !user) return ctx.reply(message || 'Error');

    ctx.reply(
        `📊 Status Akun\n\n` +
        `👤 User: ${user.code}\n` +
        `🏆 Tipe: ${user.type}\n` +
        `💳 Kredit Bulanan: ${user.monthly_credits}\n` +
        `💰 Kredit Ekstra: ${user.extra_credits}\n` +
        `📅 Expired: ${new Date(user.expired_at).toLocaleDateString()}`
    );
});

// Handle Image
bot.on('photo', async (ctx: any) => {
    const { valid, user, message } = await validateSession(ctx.from!.id);
    if (!valid) return ctx.reply(message || 'Unauthorized');

    if (!ctx.message || !('photo' in ctx.message)) return;
    const photo = ctx.message.photo[ctx.message.photo.length - 1];
    const fileLink = await ctx.telegram.getFileLink(photo.file_id);

    // Download image buffer
    const response = await axios.get(fileLink.href, { responseType: 'arraybuffer' });
    const buffer = Buffer.from(response.data);

    ctx.reply('Mengupload gambar ke server...', { reply_to_message_id: ctx.message.message_id });

    // Upload to Supabase Storage (required for some models like WAN/Runway)
    const publicUrl = await uploadImageToStorage(buffer, user!.id);

    if (!publicUrl) {
        return ctx.reply('Gagal mengupload gambar. Silakan coba lagi.');
    }

    // Default to Kling 2.1 Std, prompt user to change if needed
    userState.set(ctx.from!.id, { imageUrl: publicUrl, model: '', step: 'PROMPT' });

    ctx.reply('Gambar berhasil diupload! 📸\n\nPilih Model AI:', MODEL_KEYBOARD);
});

// Handle Model Selection
bot.action(/model_(.+)/, async (ctx: any) => {
    const model = (ctx as any).match[1];
    const state = userState.get(ctx.from!.id);

    if (!state) return ctx.reply('Sesi habis. Kirim gambar lagi.');

    state.model = model;
    userState.set(ctx.from!.id, state);

    await ctx.answerCbQuery();
    ctx.reply(`Model dipilih: ${model}\n\nSekarang balas dengan PROMPT (deskripsi video) yang diinginkan.`);
});

// Handle Text (Prompt)
bot.on('text', async (ctx: any) => {
    const messageText = ctx.message && 'text' in ctx.message ? ctx.message.text : '';
    // Check if it's a command
    if (messageText.startsWith('/')) return; // Ignore commands

    const state = userState.get(ctx.from!.id);
    if (!state || state.step !== 'PROMPT' || !state.model) {
        // If no state, maybe just chatting or invalid
        return;
    }

    const { valid, user } = await validateSession(ctx.from!.id);
    if (!valid || !user) {
        userState.delete(ctx.from!.id);
        return ctx.reply('Sesi tidak valid.');
    }

    const prompt = messageText;
    userState.delete(ctx.from!.id); // Clear state

    ctx.reply(`⏳ Sedang memproses video dengan model ${state.model}...\nPrompt: "${prompt}"\n\nMohon tunggu, ini bisa memakan waktu 3-5 menit.`);

    try {
        const { taskId, generationId, usedKey } = await processGeneration(user, state.model, prompt, state.imageUrl);

        ctx.reply(`✅ Tugas diterima! Task ID: ${taskId}\nSedang generate...`);

        // POLLING LOOP
        const maxAttempts = 60; // 5 minutes (every 5s)
        let attempts = 0;

        const pollInterval = setInterval(async () => {
            attempts++;
            const statusRes = await pollGenerationStatus(taskId, state.model, usedKey);

            if (statusRes.status === 'completed' && statusRes.videoUrl) {
                clearInterval(pollInterval);

                // Finalize (R2 Upload + DB Update)
                if (generationId) {
                    await finalizeGeneration(generationId, statusRes.videoUrl, user.id, state.model);
                }

                ctx.replyWithVideo(statusRes.videoUrl, { caption: `✅ Video Selesai!\nModel: ${state.model}\nPrompt: ${prompt}` });
            } else if (statusRes.status === 'failed') {
                clearInterval(pollInterval);
                ctx.reply(`❌ Gagal membuat video: ${statusRes.message || 'Error tidak diketahui.'}`);
            } else if (attempts >= maxAttempts) {
                clearInterval(pollInterval);
                ctx.reply('⚠️ Waktu habis (Timeout). Video mungkin masih diproses, silakan cek status nanti (Fitur cek status manual belum tersedia di bot ini).');
            }
        }, 5000);

    } catch (e: any) {
        console.error(e);
        ctx.reply(`❌ Terjadi kesalahan: ${e.message}`);
    }
});

bot.launch();

console.log('🤖 UniverseAI Bot Started!');

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));


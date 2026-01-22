"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getUserByCode = getUserByCode;
exports.getUserByTelegramId = getUserByTelegramId;
exports.loginUser = loginUser;
exports.logoutUser = logoutUser;
exports.validateSession = validateSession;
exports.takeoverSession = takeoverSession;
const supabase_js_1 = require("@supabase/supabase-js");
const config_1 = require("./config");
const supabase = (0, supabase_js_1.createClient)(config_1.config.supabase.url, config_1.config.supabase.serviceRoleKey);
async function getUserByCode(code) {
    const { data, error } = await supabase
        .from('users')
        .select('*, group:api_groups(*)')
        .eq('code', code.toUpperCase())
        .single();
    if (error || !data)
        return null;
    return data;
}
async function getUserByTelegramId(chatId) {
    const { data, error } = await supabase
        .from('users')
        .select('*, group:api_groups(*)')
        .eq('telegram_chat_id', chatId)
        .single();
    if (error || !data)
        return null;
    return data;
}
async function loginUser(code, chatId) {
    const user = await getUserByCode(code);
    if (!user) {
        return { success: false, message: 'Kode akses tidak ditemukan.' };
    }
    if (!user.status) {
        return { success: false, message: 'Akun Anda tidak aktif. Hubungi admin.' };
    }
    if (new Date(user.expired_at) < new Date()) {
        return { success: false, message: 'Kode akses Anda sudah kadaluarsa.' };
    }
    // Bind Telegram ID and set active device
    const { error } = await supabase
        .from('users')
        .update({
        telegram_chat_id: chatId,
        active_device: 'TELEGRAM',
        last_active_at: new Date().toISOString()
    })
        .eq('id', user.id);
    if (error) {
        console.error('Login error:', error);
        return { success: false, message: 'Terjadi kesalahan sistem saat login.' };
    }
    return { success: true, message: `Login berhasil! Selamat datang, ${user.code}. Sesi Web Anda (jika ada) telah diputus.`, user };
}
async function logoutUser(chatId) {
    const { error } = await supabase
        .from('users')
        .update({
        active_device: null,
        last_active_at: new Date().toISOString()
    })
        .eq('telegram_chat_id', chatId);
    if (error) {
        return { success: false, message: 'Gagal logout.' };
    }
    return { success: true, message: 'Logout berhasil. Sesi Telegram Anda berakhir.' };
}
async function validateSession(chatId) {
    const user = await getUserByTelegramId(chatId);
    if (!user) {
        return { valid: false, message: 'Anda belum login. Gunakan /login <kode_akses>' };
    }
    if (user.active_device !== 'TELEGRAM') {
        return { valid: false, message: 'Sesi Anda sedang aktif di Website. Gunakan /takeover untuk memindahkan sesi ke sini, atau logout dari Web.' };
    }
    if (!user.status || new Date(user.expired_at) < new Date()) {
        return { valid: false, message: 'Akun kadaluarsa atau tidak aktif.' };
    }
    // Refresh last active
    await supabase.from('users').update({ last_active_at: new Date().toISOString() }).eq('id', user.id);
    return { valid: true, user };
}
async function takeoverSession(chatId) {
    const user = await getUserByTelegramId(chatId);
    if (!user)
        return { success: false, message: 'Akun tidak ditemukan.' };
    await supabase
        .from('users')
        .update({
        active_device: 'TELEGRAM',
        last_active_at: new Date().toISOString()
    })
        .eq('id', user.id);
    return { success: true, message: 'Sesi berhasil diambil alih ke Telegram.' };
}

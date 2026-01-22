import { createClient } from '@supabase/supabase-js';
import { config } from './config';
import { User } from './types';

const supabase = createClient(config.supabase.url, config.supabase.serviceRoleKey);

export async function getUserByCode(code: string): Promise<User | null> {
    const { data, error } = await supabase
        .from('users')
        .select('*, group:api_groups(*)')
        .eq('code', code.toUpperCase())
        .single();

    if (error || !data) return null;
    return data as User;
}

export async function getUserByTelegramId(chatId: string | number): Promise<User | null> {
    const { data, error } = await supabase
        .from('users')
        .select('*, group:api_groups(*)')
        .eq('telegram_chat_id', chatId)
        .single();

    if (error || !data) return null;
    return data as User;
}

export async function loginUser(code: string, chatId: string | number): Promise<{ success: boolean; message: string; user?: User }> {
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

export async function logoutUser(chatId: string | number): Promise<{ success: boolean; message: string }> {
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

export async function validateSession(chatId: string | number): Promise<{ valid: boolean; user?: User; message?: string }> {
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

export async function takeoverSession(chatId: string | number): Promise<{ success: boolean; message: string }> {
    const user = await getUserByTelegramId(chatId);
    if (!user) return { success: false, message: 'Akun tidak ditemukan.' };

    await supabase
        .from('users')
        .update({
            active_device: 'TELEGRAM',
            last_active_at: new Date().toISOString()
        })
        .eq('id', user.id);

    return { success: true, message: 'Sesi berhasil diambil alih ke Telegram.' };
}

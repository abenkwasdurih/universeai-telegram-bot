import dotenv from 'dotenv';
dotenv.config();

export const config = {
    botToken: process.env.BOT_TOKEN || '',
    supabase: {
        url: process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || '',
        serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY || '',
    },
    r2: {
        accountId: process.env.R2_ACCOUNT_ID || '',
        accessKeyId: process.env.R2_ACCESS_KEY_ID || '',
        secretAccessKey: process.env.R2_SECRET_ACCESS_KEY || '',
        bucketName: process.env.R2_BUCKET_NAME || 'universeai-storage',
        publicUrl: process.env.R2_PUBLIC_URL || '',
    },
    freepik: {
        apiBase: 'https://api.freepik.com/v1/ai',
    },
    features: {
        maintenanceMode: process.env.MAINTENANCE_MODE === 'true',
    }
};

if (!config.botToken) {
    console.error('❌ BOT_TOKEN is missing in .env');
}
if (!config.supabase.url || !config.supabase.serviceRoleKey) {
    console.error('❌ Supabase credentials missing in .env');
}

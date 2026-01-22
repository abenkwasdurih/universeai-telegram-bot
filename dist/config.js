"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = void 0;
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
exports.config = {
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
if (!exports.config.botToken) {
    console.error('❌ BOT_TOKEN is missing in .env');
}
if (!exports.config.supabase.url || !exports.config.supabase.serviceRoleKey) {
    console.error('❌ Supabase credentials missing in .env');
}

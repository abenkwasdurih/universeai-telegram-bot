export type UserType = 'TRY' | 'REGULAR' | 'ADVANCE' | 'UNLIMITED';

export interface ApiGroup {
    id: string;
    name: string;
    api_keys: string[];
    defapi_key?: string | null;
    created_at: string;
    updated_at: string;
}

export interface User {
    id: string;
    code: string;
    email: string | null;
    phone: string | null;
    type: UserType;
    subscription_status: 'ACTIVE' | 'EXPIRED';
    monthly_credits: number;
    extra_credits: number;
    expired_at: string;
    allowed_models: string[] | null;
    group_id: string | null;
    user_api_key: string | null;
    status: boolean;
    created_at: string;

    // New fields for Telegram Integration
    telegram_chat_id?: string | number | null;
    active_device?: 'WEB' | 'TELEGRAM' | null;
    last_active_at?: string | null;

    // Joined
    group?: ApiGroup;
}

export interface Generation {
    id: string;
    user_id: string;
    model_name: string;
    prompt: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    video_url?: string | null;
    task_id?: string | null;
    credits_used?: number;
    api_key_used?: string;
    thumbnail_url?: string;
    created_at?: string;
}

export interface ModelPricing {
    model_id: string;
    credit_cost: number;
    billing_mode: 'CREDIT' | 'UNLIMITED' | 'PROMO';
    promo_daily_limit: number;
    unlimited_max_duration?: number | null;
}

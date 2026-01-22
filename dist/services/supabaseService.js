"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.supabase = void 0;
exports.consumeCredits = consumeCredits;
exports.logGeneration = logGeneration;
exports.getApiKeysForUser = getApiKeysForUser;
exports.getModelPricing = getModelPricing;
const supabase_js_1 = require("@supabase/supabase-js");
const config_1 = require("../config");
const supabase = (0, supabase_js_1.createClient)(config_1.config.supabase.url, config_1.config.supabase.serviceRoleKey);
exports.supabase = supabase;
// ========== SUBSCRIPTION & CREDITS ==========
async function consumeCredits(userId, amount = 1) {
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
async function logGeneration(data) {
    const { data: result, error } = await supabase
        .from('generations')
        .insert(data)
        .select()
        .single();
    if (error) {
        console.error('Error logging generation:', error);
        return null;
    }
    return result;
}
// ========== API KEYS ==========
async function getApiKeysForUser(user) {
    if (user.type === 'ADVANCE' && user.user_api_key) {
        return [user.user_api_key];
    }
    let apiKeys = [];
    if (user.group && user.group.api_keys.length > 0) {
        apiKeys = user.group.api_keys;
    }
    else {
        const { data } = await supabase
            .from('api_groups')
            .select('api_keys')
            .eq('name', 'default')
            .single();
        if (data)
            apiKeys = data.api_keys;
    }
    return apiKeys.length > 0 ? apiKeys : [];
}
async function getModelPricing(modelId) {
    const { data, error } = await supabase
        .from('ai_models')
        .select('*')
        .eq('model_id', modelId)
        .eq('is_active', true)
        .single();
    if (error)
        return null;
    return data;
}

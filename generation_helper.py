import os
import requests
import time
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Load env
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FREEPIK_API_BASE = "https://api.freepik.com/v1/ai"

MODEL_ENDPOINTS = {
    'kling-v2-1-std': {'endpoint': '/image-to-video/kling-v2-1-std', 'param': 'duration'},
    'kling-v2-1-pro': {'endpoint': '/image-to-video/kling-v2-1-pro', 'param': 'duration'},
    'kling-v2-5-pro': {'endpoint': '/image-to-video/kling-v2-5-pro', 'param': 'duration'},
    'kling-v2-6-pro': {'endpoint': '/image-to-video/kling-v2-6-pro', 'param': 'duration'},
    'kling-o1-std': {'endpoint': '/image-to-video/kling-o1-std', 'param': 'duration'},
    'kling-o1-std-video-ref': {'endpoint': '/image-to-video/kling-elements-std', 'param': 'duration'},
    'wan-v2-2-720p': {'endpoint': '/image-to-video/wan-v2-2-720p', 'param': 'duration', 'requiresHttps': True},
    'wan-v2-6-720p': {'endpoint': '/image-to-video/wan-v2-6-720p', 'param': 'duration', 'requiresHttps': True},
    'wan-v2-6-1080p': {'endpoint': '/image-to-video/wan-v2-6-1080p', 'param': 'duration', 'requiresHttps': True},
    'minimax-hailuo-02-768p': {'endpoint': '/image-to-video/minimax-hailuo-02-768p', 'param': 'duration'},
    'minimax-hailuo-02-1080p': {'endpoint': '/image-to-video/minimax-hailuo-02-1080p', 'param': 'duration'},
    'minimax-hailuo-2-3-1080p': {'endpoint': '/image-to-video/minimax-hailuo-2-3-1080p', 'param': 'duration'},
    'runway-gen4-turbo': {'endpoint': '/image-to-video/runway-gen4-turbo', 'param': 'duration', 'requiresHttps': True},
    'pixverse-v5-720p': {'endpoint': '/image-to-video/pixverse-v5', 'param': 'duration', 'requiresHttps': True},
    'seedance-pro-720p': {'endpoint': '/video/seedance-1-5-pro-720p', 'param': 'duration'},
    'seedance-pro-1080p': {'endpoint': '/video/seedance-1-5-pro-1080p', 'param': 'duration'},
    'seedance-lite-720p': {'endpoint': '/video/seedance-1-5-lite-720p', 'param': 'duration'},
    'seedance-lite-1080p': {'endpoint': '/video/seedance-1-5-lite-1080p', 'param': 'duration'},
    'kling-v1-6-pro': {'endpoint': '/image-to-video/kling-v1-6-pro', 'param': 'duration'},
    'kling-v1-6-std': {'endpoint': '/image-to-video/kling-v1-6-std', 'param': 'duration'},
}

MODEL_STATUS_ENDPOINTS = {
    'kling-v2-1-std': '/image-to-video/kling-v2-1',
    'kling-v2-1-pro': '/image-to-video/kling-v2-1',
    'kling-v2-5-pro': '/image-to-video/kling-v2-5-pro',
    'kling-v2-6-pro': '/image-to-video/kling-v2-6',
    'kling-o1-std': '/image-to-video/kling-o1',
    'kling-o1-std-video-ref': '/image-to-video/kling-elements',
    'wan-v2-2-720p': '/image-to-video/wan-v2-2-720p',
    'wan-v2-6-720p': '/image-to-video/wan-v2-6-720p',
    'wan-v2-6-1080p': '/image-to-video/wan-v2-6-1080p',
    'minimax-hailuo-02-768p': '/image-to-video/minimax-hailuo-02-768p',
    'minimax-hailuo-02-1080p': '/image-to-video/minimax-hailuo-02-1080p',
    'minimax-hailuo-2-3-1080p': '/image-to-video/minimax-hailuo-2-3-1080p',
    'runway-gen4-turbo': '/image-to-video/runway-gen4-turbo',
    'pixverse-v5-720p': '/image-to-video/pixverse-v5',
    'seedance-pro-720p': '/video/seedance-1-5-pro-720p',
    'seedance-pro-1080p': '/video/seedance-1-5-pro-1080p',
    'seedance-lite-720p': '/video/seedance-1-5-lite-720p',
    'seedance-lite-1080p': '/video/seedance-1-5-lite-1080p',
    'kling-v1-6-pro': '/image-to-video/kling-v1-6-pro',
    'kling-v1-6-std': '/image-to-video/kling-v1-6-std',
}

def get_api_keys_for_user(user):
    if user.get('type') == 'ADVANCE' and user.get('user_api_key'):
        return [user['user_api_key']]
    
    api_keys = []
    group_id = user.get('group_id')
    if group_id:
        res = supabase.table("api_groups").select("api_keys").eq("id", group_id).single().execute()
        if res.data:
            api_keys = res.data.get("api_keys", [])
    
    if not api_keys:
        res = supabase.table("api_groups").select("api_keys").eq("name", "default").single().execute()
        if res.data:
            api_keys = res.data.get("api_keys", [])
            
    return api_keys

def consume_credits(user_id, amount=1):
    res = supabase.table("users").select("monthly_credits, extra_credits").eq("id", user_id).single().execute()
    if not res.data: return False
    
    m_credits = res.data['monthly_credits']
    e_credits = res.data['extra_credits']
    
    if (m_credits + e_credits) < amount: return False
    
    remaining = amount
    if m_credits > 0:
        deduct = min(m_credits, remaining)
        m_credits -= deduct
        remaining -= deduct
    
    if remaining > 0 and e_credits > 0:
        deduct = min(e_credits, remaining)
        e_credits -= deduct
        remaining -= deduct
        
    supabase.table("users").update({"monthly_credits": m_credits, "extra_credits": e_credits}).eq("id", user_id).execute()
    return True

def process_generation(user, model_id, prompt, image_url, duration="5"):
    model_config = MODEL_ENDPOINTS.get(model_id)
    if not model_config: raise Exception("Model not found")
    
    # Get Pricing
    price_res = supabase.table("ai_models").select("credit_cost").eq("model_id", model_id).single().execute()
    credit_cost = price_res.data['credit_cost'] if price_res.data else 1
    
    # Check Credits
    if user.get('type') not in ['UNLIMITED', 'ADVANCE']:
        if not consume_credits(user['id'], credit_cost):
            raise Exception(f"Kredit tidak cukup. Butuh {credit_cost}")
    
    # Prepare Payload
    payload = {"image": image_url, "prompt": prompt}
    if "wan" in model_id: payload["size"] = "1280*720"
    if model_config.get('param') == 'duration': payload["duration"] = str(duration)
    
    if "pixverse" in model_id:
        payload = {"image_url": image_url, "prompt": prompt, "resolution": "720p", "duration": int(duration)}
        
    # Get Keys
    keys = get_api_keys_for_user(user)
    if not keys: raise Exception("Bot sedang sibuk (No API Keys)")
    
    task_id = None
    used_key = None
    
    last_error = "Unknown error"
    for key in keys:
        try:
            res = requests.post(f"{FREEPIK_API_BASE}{model_config['endpoint']}", json=payload, headers={
                "x-freepik-api-key": key,
                "Content-Type": "application/json"
            }, timeout=30)
            
            data = res.json()
            task_id = data.get("data", {}).get("task_id") or data.get("task_id")
            if task_id:
                used_key = key
                break
            else:
                last_error = data.get("message") or data.get("error") or str(data)
                print(f"API key {key[:4]}... failed: {last_error}")
        except Exception as e:
            last_error = str(e)
            print(f"API Error with key {key[:4]}: {e}")
            continue
            
    if not task_id: raise Exception(f"Semua API Key sibuk atau error: {last_error}")
    
    # Log Generation
    gen_data = {
        "user_id": user["id"],
        "model_name": model_id,
        "prompt": prompt,
        "status": "processing",
        "task_id": task_id,
        "credits_used": credit_cost,
        "api_key_used": used_key,
        "thumbnail_url": image_url
    }
    log_res = supabase.table("generations").insert(gen_data).execute()
    generation_id = log_res.data[0]['id'] if log_res.data else None
    
    print(f"DEBUG: Processing generation for {user.get('code')} using {model_id}")
    return task_id, generation_id, used_key

def poll_status(task_id, model_id, api_key):
    status_endpoint = MODEL_STATUS_ENDPOINTS.get(model_id, "/image-to-video/kling-v2-1")
    try:
        res = requests.get(f"{FREEPIK_API_BASE}{status_endpoint}/{task_id}", headers={"x-freepik-api-key": api_key}, timeout=20)
        data = res.json().get("data") or res.json()
        status = data.get("status", "").upper()
        
        if status in ["COMPLETED", "SUCCESS"]:
            video_url = None
            if data.get("generated"): video_url = data["generated"][0]
            elif data.get("video") and data["video"].get("url"): video_url = data["video"]["url"]
            elif data.get("result") and data["result"].get("url"): video_url = data["result"]["url"]
            return "completed", video_url
        elif status in ["FAILED", "ERROR"]:
            return "failed", data.get("error", "Unknown error")
        return "processing", None
    except Exception as e:
        print(f"Polling Error: {e}")
        return "error", str(e)

def finalize_generation(generation_id, video_url, user_id, r2_url=None):
    supabase.table("generations").update({
        "status": "completed",
        "video_url": video_url,
        "r2_url": r2_url or video_url
    }).eq("id", generation_id).execute()
    
    # Increment count
    supabase.rpc("increment_video_count", {"user_id": user_id}).execute()

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
    'seedance-1-5-pro-720p': {'endpoint': '/video/seedance-1-5-pro-720p', 'param': 'duration'},
    'seedance-pro-1080p': {'endpoint': '/video/seedance-1-5-pro-1080p', 'param': 'duration'},
    'seedance-lite-720p': {'endpoint': '/video/seedance-1-5-lite-720p', 'param': 'duration'},
    'seedance-lite-1080p': {'endpoint': '/video/seedance-1-5-lite-1080p', 'param': 'duration'},
    'kling-v1-6-pro': {'endpoint': '/image-to-video/kling-pro', 'param': 'duration'},
    'kling-v1-6-pro': {'endpoint': '/image-to-video/kling-pro', 'param': 'duration'},
    'kling-v1-6-std': {'endpoint': '/image-to-video/kling-std', 'param': 'duration'},
    'kling-v2-6-motion-control-pro': {'endpoint': '/video/kling-v2-6-motion-control-pro', 'param': 'options'},
    'kling-v2-6-motion-control-std': {'endpoint': '/video/kling-v2-6-motion-control-std', 'param': 'options'},

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
    'seedance-1-5-pro-720p': '/video/seedance-1-5-pro-720p',
    'seedance-pro-720p': '/video/seedance-1-5-pro-720p',
    'seedance-pro-1080p': '/video/seedance-1-5-pro-1080p',
    'seedance-lite-720p': '/video/seedance-1-5-lite-720p',
    'seedance-lite-1080p': '/video/seedance-1-5-lite-1080p',
    'kling-v1-6-pro': '/image-to-video/kling',
    'kling-v1-6-std': '/image-to-video/kling',
}

def get_api_keys_for_user(user):
    if user.get('type') == 'ADVANCE' and user.get('user_api_key'):
        return [user['user_api_key']]
    
    api_keys = []
    group_id = user.get('group_id')
    if group_id:

        res = supabase.table("api_groups").select("api_keys").eq("id", group_id).limit(1).execute()
        if res.data:
            api_keys = res.data[0].get("api_keys", [])
    
    if not api_keys:
        res = supabase.table("api_groups").select("api_keys").eq("name", "default").limit(1).execute()
        if res.data:
            api_keys = res.data[0].get("api_keys", [])
            
    return [k.split('|')[0].strip() for k in api_keys]

def consume_credits(user_id, amount=1):
    res = supabase.table("users").select("monthly_credits, extra_credits").eq("id", user_id).limit(1).execute()
    if not res.data: return False
    
    m_credits = res.data[0]['monthly_credits']
    e_credits = res.data[0]['extra_credits']
    
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
    # Ensure model_name is lowercase as requested
    model_id = model_id.lower()
    
    model_config = MODEL_ENDPOINTS.get(model_id)
    if not model_config: raise Exception("Model not found")
    
    # Get Pricing
    price_res = supabase.table("ai_models").select("credit_cost").eq("model_id", model_id).limit(1).execute()
    credit_cost = price_res.data[0]['credit_cost'] if price_res.data else 1
    
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
            full_url = f"{FREEPIK_API_BASE}{model_config['endpoint']}"
            
            # Request logging
            print(f"DEBUG: 🚀 Sending Request to: {full_url}")
            print(f"DEBUG: 📦 Payload: {payload}")
            
            res = requests.post(full_url, json=payload, headers={
                "x-freepik-api-key": key,
                "Content-Type": "application/json"
            }, timeout=30)
            
            data = res.json()
            task_id = data.get("data", {}).get("task_id") or data.get("task_id")
            
            if res.status_code == 200 and task_id:
                used_key = key
                break
            else:
                last_error = data.get("message") or data.get("error") or str(data)
                print(f"❌ API result with key {key[:4]}... (Status: {res.status_code}): {last_error}")
                
                # Log full payload on 404 or 422 for debugging
                if res.status_code in [404, 422]:
                    print(f"⚠️ Full Payload sent to Freepik: {payload}")
                    if res.status_code == 404:
                         print(f"❌ 404 Not Found Body: {res.text}")
        except Exception as e:
            last_error = str(e)
            print(f"❌ Exception with key {key[:4]}: {e}")
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

    # --- NEW: Insert into tasks table for tracking ---
    try:
        task_data = {
            "user_id": user["id"],
            "prompt": prompt,
            "status": "processing",
            "source": "telegram",
            "file_url": image_url,
            "telegram_chat_id": str(user.get("telegram_id", "")),
            
            # Requested Defaults
            # Fallback if missing
            "model_name": model_id if model_id else "kling-v1-6-std",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "created_at": "now()"
        }
        supabase.table("tasks").insert(task_data).execute()
        print(f"DEBUG: Task inserted into 'tasks' table.")
    except Exception as e:
        print(f"⚠️ Failed to insert into tasks table: {e}")

    return task_id, generation_id, used_key

def poll_status(task_id, model_id, api_key):
    model_id = model_id.lower() if model_id else model_id
    status_endpoint = MODEL_STATUS_ENDPOINTS.get(model_id, "/image-to-video/kling-v2-1")
    try:
        res = requests.get(f"{FREEPIK_API_BASE}{status_endpoint}/{task_id}", headers={"x-freepik-api-key": api_key}, timeout=20)
        
        data = res.json().get("data") or res.json()
        status = data.get("status", "").upper()
        
        print(f"DEBUG: 🔄 [Poll] Task: {task_id[:6]}... | Parse Status: {status}")
        if status in ["COMPLETED", "SUCCESS"]:
            print(f"DEBUG: ✅ Completed Data: {data}")
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

def submit_freepik_task(user, model_id, prompt, image_url, duration="5", options=None):
    """
    Submits a task to Freepik API using available keys.
    Returns: (task_id, used_key) or raises Exception.
    Does NOT handle DB logging or credit consumption.
    """
    options = options or {}
    # Ensure model_name is lowercase
    model_id = model_id.lower()
    
    model_config = MODEL_ENDPOINTS.get(model_id)
    if not model_config: raise Exception(f"Model {model_id} not found")

    # Prepare Payload
    if 'motion-control' in model_id:
        # Specific payload for Motion Control
        payload = {
            "image_url": image_url,
            "video_url": options.get('driving_url') or options.get('video_url'),
            "prompt": prompt,
            "character_orientation": options.get('character_orientation', 'video'),
            "cfg_scale": float(options.get('cfg_scale', 0.5))
        }
    elif 'seedance' in model_id:
        # Seedance Aspect Ratio Mapping
        ratio_map = {
            '16:9': 'widescreen_16_9',
            '9:16': 'social_story_9_16',
            '1:1': 'square_1_1',
            '4:3': 'classic_4_3', 
            '3:4': 'traditional_3_4',
            '21:9': 'film_horizontal_21_9',
            '9:21': 'film_vertical_9_21'
        }
        
        ar = options.get('aspect_ratio', '16:9')
        mapped_ar = ratio_map.get(ar, 'widescreen_16_9')
        
        payload = {
            "image": image_url,
            "prompt": prompt,
            "duration": int(duration), # Spec says integer
            "aspect_ratio": mapped_ar,
            "generate_audio": True
        }
    else:
        # Standard payload
        payload = {"image": image_url, "prompt": prompt}
        if "wan" in model_id: payload["size"] = "1280*720"
        if model_config.get('param') == 'duration': payload["duration"] = str(duration)
        
        if "pixverse" in model_id:
            payload = {"image_url": image_url, "prompt": prompt, "resolution": "720p", "duration": int(duration)}
            
        # Add generic options if available
        if options.get('negative_prompt'): payload['negative_prompt'] = options['negative_prompt']
        if options.get('cfg_scale'): payload['cfg_scale'] = float(options['cfg_scale'])
        if options.get('aspect_ratio'): payload['aspect_ratio'] = options['aspect_ratio']

    # Get Keys
    keys = get_api_keys_for_user(user)
    if not keys: raise Exception("Bot sedang sibuk (No API Keys)")
    
    task_id = None
    used_key = None
    last_error = "Unknown error"
    
    for key in keys:
        try:
            full_url = f"{FREEPIK_API_BASE}{model_config['endpoint']}"
            
            # Request logging
            print(f"DEBUG: 🚀 [Worker] Sending Request to: {full_url}")
            
            res = requests.post(full_url, json=payload, headers={
                "x-freepik-api-key": key,
                "Content-Type": "application/json"
            }, timeout=30)
            
            data = res.json()
            task_id = data.get("data", {}).get("task_id") or data.get("task_id")
            
            if res.status_code == 200 and task_id:
                used_key = key
                break
            else:
                last_error = data.get("message") or data.get("error") or str(data)
                print(f"❌ [Worker] API result with key {key[:4]}... (Status: {res.status_code}): {last_error}")
                if res.status_code == 429: # Rate limit
                    continue # Try next key
                
        except Exception as e:
            last_error = str(e)
            print(f"❌ [Worker] Exception with key {key[:4]}: {e}")
            continue
            
    if not task_id: raise Exception(f"Gagal submi API: {last_error}")
    
    return task_id, used_key

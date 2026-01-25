def submit_freepik_task(user, model_id, prompt, image_url, duration="5"):
    """
    Submits a task to Freepik API using available keys.
    Returns: (task_id, used_key) or raises Exception.
    Does NOT handle DB logging or credit consumption.
    """
    # Ensure model_name is lowercase
    model_id = model_id.lower()
    
    model_config = MODEL_ENDPOINTS.get(model_id)
    if not model_config: raise Exception(f"Model {model_id} not found")

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
            
    if not task_id: raise Exception(f"Gagal submit ke API: {last_error}")
    
    return task_id, used_key

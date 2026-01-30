import asyncio
from datetime import datetime, timedelta, timezone

async def check_cooldown(supabase_client, user_id: str, user_type: str, model_name: str) -> tuple[bool, str]:
    """
    Check if user is in cooldown period dynamically.
    Args:
        supabase_client: Initialized Supabase client
        user_id: User's UUID
        user_type: 'PRO', 'UNLIMITED', 'ADVANCE'
        model_name: Name of the model
    Returns (is_allowed, message).
    """
    # Only applies to Kling Motion Control
    if 'motion-control' not in model_name:
        return True, ""

    try:
        # 1. Fetch latest stats
        # Real DB call using provided client
        response = supabase_client.table('users').select('total_gen_cycle,last_generation_time').eq('id', user_id).execute()
        
        # Check if response has data (supabase-py format usually response.data)
        data = response.data if hasattr(response, 'data') else response
        
        if not data or len(data) == 0:
            return True, ""
            
        user_data = data[0]

        last_gen_iso = user_data.get('last_generation_time')
        current_cycle = user_data.get('total_gen_cycle', 0) or 0
        
        # 2. Lazy Reset Logic (Check Day Change)
        utc_now = datetime.now(timezone.utc)
        wib_now = utc_now + timedelta(hours=7)
        
        if last_gen_iso:
            last_gen_dt = datetime.fromisoformat(str(last_gen_iso).replace('Z', '+00:00'))
            last_gen_wib = last_gen_dt.astimezone(timezone(timedelta(hours=7)))
            
            # If day changed, reset cycle logically
            if last_gen_wib.date() != wib_now.date():
                current_cycle = 0
                last_gen_wib = None
        
        # 3. Check Cooldown Trigger (Multiples of 3)
        if current_cycle > 0 and current_cycle % 3 == 0:
            
            # Determine Wait Time
            wait_minutes = 0
            
            if user_type == 'UNLIMITED' or user_type == 'ULTRA':
                # Exponential: 30 * 2^((cycle/3) - 1)
                exponent = (current_cycle // 3) - 1
                wait_minutes = 30 * (2 ** exponent)
                wait_minutes = min(wait_minutes, 1440) # Safety cap 24h
            elif user_type in ['PRO', 'ADVANCE']:
                # Fixed 15 minutes
                wait_minutes = 15
            else:
                return True, "" 

            # Calculate Remaining Time
            if last_gen_iso:
                last_gen_dt = datetime.fromisoformat(str(last_gen_iso).replace('Z', '+00:00'))
                elapsed = utc_now - last_gen_dt
                elapsed_minutes = elapsed.total_seconds() / 60
                
                remaining_minutes = wait_minutes - elapsed_minutes
                
                if remaining_minutes > 0:
                    # Format readable time
                    rem_min = int(remaining_minutes)
                    rem_sec = int((remaining_minutes - rem_min) * 60)
                    
                    msg = (
                        f"⏳ **Cooldown Mode**\n\n"
                        f"Anda telah mencapai batas {current_cycle} generate berturut-turut.\n"
                        f"Istirahat dulu ya! Silakan kembali dalam:\n"
                        f"⏳ **{rem_min} menit {rem_sec} detik**"
                    )
                    return False, msg

        return True, ""

    except Exception as e:
        print(f"Error checking cooldown: {e}")
        return True, ""

async def update_user_cooldown(supabase_client, user_id: str, model_name: str):
    """
    Update data cooldown user(total_gen_cycle) after successful submit.
    Also handles "Lazy Reset" by checking day change before incrementing.
    """
    # Only applies to Kling Motion Control
    if 'motion-control' not in model_name:
        return

    try:
        res = supabase_client.table("users").select("total_gen_cycle, last_generation_time").eq("id", user_id).execute()
        if not res.data:
            return
            
        user = res.data[0]
        current_cycle = user.get("total_gen_cycle", 0) or 0
        last_gen_iso = user.get("last_generation_time")
        
        utc_now = datetime.now(timezone.utc)
        wib_now = utc_now + timedelta(hours=7)
        
        # Check Day Change for Reset
        if last_gen_iso:
            last_gen_dt = datetime.fromisoformat(str(last_gen_iso).replace('Z', '+00:00'))
            last_gen_wib = last_gen_dt.astimezone(timezone(timedelta(hours=7)))
            
            if last_gen_wib.date() != wib_now.date():
                current_cycle = 0
        
        # Increment
        new_cycle = current_cycle + 1
        
        # Update
        supabase_client.table("users").update({
            "total_gen_cycle": new_cycle,
            "last_generation_time": "now()"
        }).eq("id", user_id).execute()
        
    except Exception as e:
        print(f"Update Cooldown Error: {e}")

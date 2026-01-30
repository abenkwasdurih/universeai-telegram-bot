import asyncio
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
import os
import json
from dotenv import load_dotenv
from generation_helper import submit_freepik_task, consume_credits

# Load env variables (re-load to ensure worker has them)
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
GLOBAL_DELAY_SECONDS = 5
MAX_GLOBAL_CONCURRENT = 12
MAX_USER_CONCURRENT_LIMIT = {
    'UNLIMITED': 3, 
    'ULTRA': 3, 
    'ADVANCE': 3, 
    'PRO': 2, 
    'DEFAULT': 1
}

# Cache for rate limiting
last_global_request_time = 0

async def check_user_concurrency(user_id, user_type):
    """Check if user has exceeded their concurrent limit."""
    limit = MAX_USER_CONCURRENT_LIMIT.get(user_type, MAX_USER_CONCURRENT_LIMIT['DEFAULT'])
    
    # --- STALE TASK CLEANUP ---
    # Automatically fail processing tasks older than 10 minutes
    ten_mins_ago = (datetime.now() - timedelta(minutes=10)).isoformat()
    try:
        # 1. Identify stale tasks
        stale_res = supabase.table("generations") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("status", "processing") \
            .lt("created_at", ten_mins_ago) \
            .execute()
        
        if stale_res.data:
            stale_ids = [d['id'] for d in stale_res.data]
            logger.warning(f"[WORKER] Cleaning up {len(stale_ids)} stale tasks for User {user_id}")
            # 2. Mark as failed
            supabase.table("generations") \
                .update({"status": "failed", "error": "Task timed out (stale)"}) \
                .in_("id", stale_ids) \
                .execute()
    except Exception as e:
        logger.error(f"[WORKER] Error cleaning up stale tasks for {user_id}: {e}")

    # Count active jobs for this user
    try:
        res = supabase.table("generations").select("id", count="exact").eq("user_id", user_id).eq("status", "processing").execute()
        count = res.count if res.count is not None else 0
        logger.info(f"👤 User [{user_id}] memiliki [{count}] tugas aktif (Limit: {limit})")
    except Exception as e:
        logger.error(f"[WORKER] Error checking user concurrency for {user_id}: {e}")
        count = 0 
    
    return count < limit

async def check_global_concurrency():
    """Check if server is under high load (only counting RECENT tasks)."""
    # Only count tasks in 'processing' status that were created in the last 15 minutes.
    # This prevents old hung tasks from blocking the queue forever.
    fifteen_mins_ago = (datetime.now() - timedelta(minutes=15)).isoformat()
    
    try:
        res = supabase.table("generations").select("id", count="exact") \
            .eq("status", "processing") \
            .gte("created_at", fifteen_mins_ago) \
            .execute()
        count = res.count if res.count is not None else 0
    except Exception as e:
        logger.error(f"[WORKER] Error checking global concurrency: {e}")
        count = 0
    
    
    if count >= MAX_GLOBAL_CONCURRENT:
        logger.warning(f"[WORKER] Global concurrency limit reached ({count}/{MAX_GLOBAL_CONCURRENT}). Waiting for recent tasks to finish.")
        return False
        
    return True

async def worker_loop(application):
    """
    Main background loop.
    application: The python-telegram-bot Application instance (for scheduling callbacks).
    """
    global last_global_request_time
    logger.info("👷 Queue Worker Started!")
    heartbeat_time = 0

    while True:
        try:
            now = datetime.now().timestamp()
            
            # Initialize loop variables to avoid NameError if exceptions occur early
            api_task_id = None
            used_key = None
            last_global_error = None
            
            # Heartbeat every 30s
            if now - heartbeat_time > 30:
                logger.info("[WORKER HEARTBEAT] Worker is alive and checking for tasks...")
                heartbeat_time = now

            # 1. Enforce Global Delay
            time_since_last = now - last_global_request_time
            if time_since_last < GLOBAL_DELAY_SECONDS:
                await asyncio.sleep(0.5)
                continue

            # 2. Check Global Load
            if not await check_global_concurrency():
                logger.info("[WORKER] Global concurrency limit reached. Waiting...")
                await asyncio.sleep(2) 
                continue

            # 3. Fetch ONE oldest Pending Task from Telegram source in generations table
            try:
                res = supabase.table("generations").select("*, users(*)").eq("status", "pending").eq("source", "telegram") \
                    .order("created_at").limit(1).execute()
            except Exception as e:
                logger.error(f"[WORKER] Error fetching pending tasks from generations: {e}")
                await asyncio.sleep(5)
                continue
            
            if not res.data:
                await asyncio.sleep(2) 
                continue

            task = res.data[0]
            logger.info(f"[WORKER] Found pending task ID: {task['id']} | User ID: {task['user_id']}")
            user = task['users'] 
            
            # flatten user data if list (supabase-py sometimes returns list for joined)
            if isinstance(user, list): user = user[0] 

            # 4. Check User Concurrency
            if not await check_user_concurrency(task['user_id'], user.get('type')):
                # User is busy. We should skip this task for now and maybe try another?
                # For simplicity in V1: we just wait. In real queue, we'd pick next task from diff user.
                # To prevent blocking queue, we could check next tasks, but let's just wait a bit.
                logger.info(f"⏳ User {user.get('code')} hit limit. Waiting...")
                await asyncio.sleep(2)
                continue

            # 5. EXECUTE TASK
            model_id = task.get('model_name', 'kling-v1-6-std')
            logger.info(f"🚀 Starting Task {task['id']} for {user.get('code')} (Model: {model_id})")
            
            try:
                # Get Price from DB to check Credits
                try:
                    price_res = supabase.table("ai_models").select("*").eq("model_id", model_id).execute()
                except Exception as e:
                    logger.error(f"[WORKER] Database error fetching model cost: {e}")
                    price_res = None
                
                if not price_res.data:
                    logger.error(f"[WORKER] Model ID '{model_id}' not found in ai_models table! Using default cost=0.")
                    credit_cost = 0
                else:
                    m_data = price_res.data[0]
                    # Determine cost based on duration in task options
                    # Default duration is 5 if not specified
                    task_options_temp = task.get('options') or task.get('metadata') or task.get('task_metadata') or {}
                    if isinstance(task_options_temp, str):
                        try:
                            task_options_temp = json.loads(task_options_temp)
                        except:
                            task_options_temp = {}
                    
                    duration = str(task_options_temp.get('duration', '5'))
                    
                    is_free_5s = m_data.get('is_free_pro_5s', False)
                    base_cost = m_data.get('credit_cost') or 0
                    
                    # Pricing logic with fallback: Try specific -> Try Pro -> Try Base/Legacy
                    cost_5s = int(m_data.get('cost_pro_5s') or m_data.get('cost_pro') or base_cost or 0)
                    cost_10s = int(m_data.get('cost_pro_10s') or m_data.get('cost_pro') or (base_cost * 2) or 0)
                    
                    if duration == '5':
                         credit_cost = 0 if is_free_5s else cost_5s
                    else:
                         credit_cost = cost_10s

                if user.get('type') not in ['UNLIMITED', 'ADVANCE']:
                    if not consume_credits(user['id'], credit_cost):
                         # Failed credits
                         logger.error(f"❌ User {user.get('code')} ran out of credits in queue.")
                         try:
                             supabase.table("generations").update({"status": "failed", "error": "Insufficient credits"}).eq("id", task['id']).execute()
                         except Exception as db_e:
                             logger.error(f"[WORKER] Failed to update generation status to failed: {db_e}")
                         
                         if task.get("telegram_chat_id"):
                             await application.bot.send_message(chat_id=task["telegram_chat_id"], text="❌ Gagal: Kredit tidak mencukupi saat giliran Anda tiba.")
                         continue

                # Update status to PROCESSING immediately to lock it
                try:
                    supabase.table("generations").update({"status": "processing"}).eq("id", task['id']).execute()
                except Exception as e:
                    logger.error(f"[WORKER] Failed to lock generation record {task['id']} as processing: {e}")
                    # If we can't lock it, we might want to skip to avoid double processing
                    continue
                
                last_global_request_time = datetime.now().timestamp() # Reset timer

                # Notify Telegram: Processing
                if task.get("telegram_chat_id"):
                   pass 

                # --- NEW: SUBMIT TASK TO API ---
                # api_task_id already initialized at top of loop
                
                try:
                    # generation_helper usually expects image_url.
                    # In 'generations' table it might be in 'thumbnail_url' or we use 'file_url' from 'tasks' if we had it.
                    # The worker fetched from 'generations'. Let's check available fields.
                    # Based on generation_helper.py:180, 'thumbnail_url' is used for image_url.
                    img_url = task.get('thumbnail_url') 
                    
                    # If not in thumbnail_url, try to find it elsewhere or fail.
                    if not img_url:
                        # Fallback: maybe it's in the 'image' field if schema differs? 
                        # Or 'video_url' if it's vid2vid? 
                        # For now assume thumbnail_url is the source image.
                        logger.warning(f"[WORKER] thumbnail_url is empty for task {task['id']}. Checking other fields.")
                        # Minimal fallback if users table has something? Unlikely.
                        pass

                    if not img_url:
                         raise Exception("Source image URL (thumbnail_url) is missing.")

                    prompt = task.get('prompt')
                    duration = str(task.get('duration', '5')) # Default '5'
                    
                    task_options = task.get('options') or task.get('metadata') or task.get('task_metadata') or {}
                    if isinstance(task_options, str):
                        try:
                            task_options = json.loads(task_options)
                        except:
                            task_options = {}

                    # Ensure aspect_ratio is passed
                    if task.get('aspect_ratio'):
                        task_options['aspect_ratio'] = task.get('aspect_ratio')


                    # Submit
                    api_task_id, used_key = submit_freepik_task(
                        user=user,
                        model_id=model_id,
                        prompt=prompt,
                        image_url=img_url,
                        duration=duration,
                        options=task_options
                    )
                except Exception as api_e:
                    logger.error(f"[WORKER] API Submission Failed for {task['id']}: {api_e}")
                    last_global_error = str(api_e)
                    api_task_id = None

                # CHECK IF WE GOT A TASK ID
                if api_task_id:
                    # Update generation record with API info
                    try:
                        supabase.table("generations").update({
                            "task_id": api_task_id,
                            "api_key_used": used_key,
                            "credits_used": credit_cost,
                            "aspect_ratio": task.get('aspect_ratio', '16:9')
                        }).eq("id", task['id']).execute()
                        logger.info(f"[WORKER] Generation {task['id']} updated with API details.")
                    except Exception as e:
                        logger.error(f"[WORKER] Database update error for generation {task['id']}: {e}")
                    
                    
                    # SCHEDULE POLLING
                    poll_callback = application.bot_data.get("poll_status_callback")
                    if poll_callback:
                        chat_id = int(task['telegram_chat_id']) if task.get('telegram_chat_id') else None
                        
                        if chat_id:
                            # Msg ID handling
                            msg_id = task.get('options', {}).get('msg_id')
                            if msg_id:
                                try:
                                    await application.bot.edit_message_text(
                                        chat_id=chat_id,
                                        message_id=msg_id,
                                        text="🚀 **Permintaan Diproses!**\nSedang menghubungkan ke server...",
                                        parse_mode='Markdown'
                                    )
                                except Exception as e:
                                    logger.warning(f"[WORKER] Failed to edit message: {e}")
                            else:
                                logger.info("[WORKER] No msg_id found, sending new message")
                                try:
                                    sent_msg = await application.bot.send_message(
                                        chat_id=chat_id, 
                                        text="🚀 **Permintaan Diproses!**\nSedang menghubungkan ke server...",
                                        parse_mode='Markdown'
                                    )
                                    msg_id = sent_msg.message_id
                                except Exception as e:
                                    logger.error(f"[WORKER] Failed to send new message: {e}")

                            application.job_queue.run_repeating(
                                poll_callback, 
                                interval=5, 
                                first=1, 
                                data={
                                    "task_id": api_task_id, 
                                    "gen_id": task['id'], 
                                    "used_key": used_key,
                                    "model_id": model_id,
                                    "chat_id": chat_id, 
                                    "msg_id": msg_id, 
                                    "prompt": task['prompt'],
                                    "user_id": user['id'],
                                    "start_time": datetime.now(),
                                    "credits_used": task.get('options', {}).get('credits_used', credit_cost)
                                },
                                name=f"poll_{api_task_id}"
                            )
                            logger.info(f"✅ Executed & Polling started for {api_task_id}")
                        else:
                             # No chat_id, but task started. Logic?
                             logger.info(f"✅ Executed for {api_task_id} (No Telegram Chat ID)")
                             
                else:
                    # FAILURE HANDLING
                    err_msg = last_global_error if last_global_error else "Unknown API Error"
                    logger.error(f"[WORKER] Failed to get API ID for task {task['id']}. Marking as failed.")
                    
                    try:
                        supabase.table("generations").update({
                            "status": "failed", 
                            "error": f"API Error: {err_msg}"
                        }).eq("id", task['id']).execute()
                    except Exception as db_e:
                        logger.error(f"[WORKER] Failed to update status to failed: {db_e}")
                    
                    if task.get("telegram_chat_id"):
                         try:
                             await application.bot.send_message(
                                 chat_id=task["telegram_chat_id"], 
                                 text=f"❌ Gagal memproses permintaan: {err_msg}"
                             )
                         except Exception as send_e:
                             logger.error(f"[WORKER] Failed to send failure notification: {send_e}")
                    continue

            except Exception as e:
                logger.error(f"[WORKER] Failed to execute task {task['id']}: {e}", exc_info=True)
                try:
                    supabase.table("generations").update({"status": "failed", "error": str(e)}).eq("id", task['id']).execute()
                except Exception as db_e:
                    logger.error(f"[WORKER] Double failure: Could not update generation status: {db_e}")
                if task.get("telegram_chat_id"):
                    await application.bot.send_message(chat_id=task["telegram_chat_id"], text=f"❌ Gagal memproses: {str(e)}")

        except Exception as e:
            logger.error(f"[WORKER] Worker Loop Error: {e}", exc_info=True)
            await asyncio.sleep(5)

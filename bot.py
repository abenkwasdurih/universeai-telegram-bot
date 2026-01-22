import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)
from supabase import create_client, Client
from r2_helper import R2Helper
from generation_helper import process_generation, poll_status, finalize_generation

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize R2 Helper
r2 = R2Helper()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for ConversationHandler
(
    AWAITING_ACCESS_CODE,
    DASHBOARD,
    SELECTING_MODEL,
    SELECTING_DURATION,
    AWAITING_MEDIA,
) = range(5)

# --- Helpers ---

def get_user_by_telegram_id(chat_id):
    res = supabase.table("users").select("*").eq("telegram_id", str(chat_id)).execute()
    return res.data[0] if res.data else None

def get_active_models():
    res = supabase.table("ai_models").select("model_id, display_name").eq("is_active", True).order("sort_order").execute()
    return res.data if res.data else []

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point /start."""
    chat_id = update.effective_chat.id
    user = get_user_by_telegram_id(chat_id)

    if user:
        return await show_dashboard(update, context, user)

    await update.message.reply_text(
        "Selamat datang di UniverseAI Video Generator Bot! 🤖\n\n"
        "Silakan masukkan **Kode Akses** Anda untuk memulai."
    )
    return AWAITING_ACCESS_CODE

async def handle_access_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Login logic."""
    access_code = update.message.text.strip().upper()
    chat_id = update.effective_chat.id

    try:
        res = supabase.table("users").select("*").eq("code", access_code).execute()
        if not res.data:
            await update.message.reply_text("❌ Kode akses tidak ditemukan. Silakan coba lagi.")
            return AWAITING_ACCESS_CODE
            
        user = res.data[0]
        
        # Link Telegram ID
        supabase.table("users").update({
            "active_platform": "telegram",
            "telegram_id": str(chat_id)
        }).eq("id", user["id"]).execute()
        
        # Notify user of success
        await update.message.reply_text("🔓 **Login Berhasil!**", parse_mode='Markdown')
        
        return await show_dashboard(update, context, user)

    except Exception as e:
        logger.error(f"Login error: {e}")
        await update.message.reply_text("Terjadi kesalahan sistem.")
        return AWAITING_ACCESS_CODE

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None) -> int:
    """Display user info and main menu."""
    if not user:
        user = get_user_by_telegram_id(update.effective_chat.id)
    
    if not user: # Safety
        return await start(update, context)

    expired_at = user.get("expired_at", "Tidak ada data")
    if expired_at and expired_at != "Tidak ada data":
        try:
            dt = datetime.fromisoformat(expired_at.replace('Z', '+00:00'))
            expired_at = dt.strftime("%d %b %Y")
        except: pass

    text = (
        f"👤 **Selamat Datang:** {user.get('code')}\n"
        f"📅 **Masa Aktif:** {expired_at}\n"
        f"💎 **Tipe User:** {str(user.get('type', 'Free')).upper()}\n"
        f"🪙 **Sisa Kredit:** {user.get('credits', 0) if user.get('credits') is not None else user.get('monthly_credits', 0)}\n\n"
        "Pilih menu di bawah ini:"
    )
    
    keyboard = [[InlineKeyboardButton("🚀 Buat Video Sekarang", callback_data="create_video")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg_args = {"text": text, "reply_markup": reply_markup, "parse_mode": 'Markdown'}
    if update.message:
        await update.message.reply_text(**msg_args)
    else:
        await update.callback_query.message.reply_text(**msg_args)
    
    return DASHBOARD

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle DASHBOARD button clicks."""
    query = update.callback_query
    await query.answer()

    if query.data == "create_video":
        models = get_active_models()
        if not models:
            await query.edit_message_text("Maaf, saat ini tidak ada model yang aktif.")
            return DASHBOARD
        
        keyboard = []
        row = []
        for i, m in enumerate(models):
            row.append(InlineKeyboardButton(m['display_name'], callback_data=f"model_{m['model_id']}"))
            if len(row) == 2: # 2 columns
                keyboard.append(row)
                row = []
        if row: # remaining
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🤖 **Pilih Model AI:**", reply_markup=reply_markup, parse_mode='Markdown')
        return SELECTING_MODEL

async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle model selection."""
    query = update.callback_query
    await query.answer()
    
    model_id = query.data.replace("model_", "")
    context.user_data['selected_model'] = model_id
    
    # Standard duration options
    durations = ["5", "10"]
    
    keyboard = [[InlineKeyboardButton(f"{d} Detik", callback_data=f"dur_{d}") for d in durations]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"⏱ **Pilih Durasi ({model_id}):**", reply_markup=reply_markup, parse_mode='Markdown')
    return SELECTING_DURATION

async def select_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle duration selection."""
    query = update.callback_query
    await query.answer()
    
    duration = query.data.replace("dur_", "")
    context.user_data['selected_duration'] = duration
    
    await query.edit_message_text(
        "📸 **Instruksi Upload:**\n\n"
        "Silakan kirimkan **1 Foto** dan tambahkan **Caption** sebagai prompt instruksi video Anda."
    )
    return AWAITING_MEDIA

async def handle_media_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute Video Generation."""
    if not update.message.photo:
        await update.message.reply_text("Harap kirimkan foto.")
        return AWAITING_MEDIA
    
    photo = update.message.photo[-1]
    prompt = update.message.caption or ""
    
    if not prompt:
        await update.message.reply_text("⚠️ Anda harus menyertakan **Caption** sebagai prompt.")
        return AWAITING_MEDIA

    chat_id = update.effective_chat.id
    user = get_user_by_telegram_id(chat_id)
    model_id = context.user_data.get('selected_model')
    duration = context.user_data.get('selected_duration')

    # Loading Message
    status_msg = await update.message.reply_text("🚀 Menyiapkan proses generate...")
    
    try:
        # 1. Download & Upload to R2
        await status_msg.edit_text("⏳ Mengunggah gambar ke storage...")
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        
        file_name = f"tele_{chat_id}_{int(datetime.now().timestamp())}.jpg"
        image_url = r2.upload_bytes(photo_bytes, file_name, content_type='image/jpeg')
        
        if not image_url:
            await status_msg.edit_text("❌ Gagal mengunggah gambar ke storage.")
            return ConversationHandler.END

        # 2. Call Generation API (Freepik via Helper)
        await status_msg.edit_text("🤖 Mengirim permintaan ke AI Model...")
        task_id, gen_id, used_key = process_generation(user, model_id, prompt, image_url, duration)
        
        # 3. Start Polling Job
        context.job_queue.run_repeating(
            poll_status_job, 
            interval=5, 
            first=2, 
            data={
                "task_id": task_id, 
                "gen_id": gen_id,
                "used_key": used_key,
                "model_id": model_id,
                "chat_id": chat_id, 
                "msg_id": status_msg.message_id,
                "prompt": prompt,
                "user_id": user['id'],
                "start_time": datetime.now()
            },
            name=f"poll_{task_id}"
        )
        
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Generate Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        return ConversationHandler.END

async def poll_status_job(context: ContextTypes.DEFAULT_TYPE):
    """Update loading visuals and handle final video."""
    job = context.job
    d = job.data
    
    elapsed = int((datetime.now() - d["start_time"]).total_seconds())
    progress = min(98, (elapsed * 2)) 
    bar = "▓" * (progress // 10) + "░" * (10 - (progress // 10))
    
    try:
        status, video_url = poll_status(d["task_id"], d["model_id"], d["used_key"])
        
        if status == "completed" and video_url:
            await context.bot.edit_message_text(
                f"✅ **Video Selesai!** ({elapsed}s)\nSedang memproses file akhir...",
                chat_id=d["chat_id"], message_id=d["msg_id"], parse_mode='Markdown'
            )
            
            # Finalize (Upload Video to R2 + Update DB)
            video_name = f"gen_video_{d['gen_id']}.mp4"
            r2_video_url = r2.upload_from_url(video_url, video_name, content_type='video/mp4')
            
            finalize_generation(d["gen_id"], video_url, d["user_id"], r2_video_url)
            
            final_url = r2_video_url or video_url
            await context.bot.send_video(
                chat_id=d["chat_id"], 
                video=final_url, 
                caption=f"🎬 **Video Hasil Generate**\n\nModel: `{d['model_id']}`\nPrompt: \"{d['prompt']}\"",
                parse_mode='Markdown'
            )
            job.schedule_removal()
            return

        elif status == "failed":
            await context.bot.edit_message_text(f"❌ Gagal: {video_url}", chat_id=d["chat_id"], message_id=d["msg_id"])
            job.schedule_removal()
            return
            
        # Update progress visual
        await context.bot.edit_message_text(
            f"🎬 **Video sedang di-generate...**\n\n`[{bar}] {progress}%`\nWaktu berjalan: {elapsed} detik",
            chat_id=d["chat_id"], message_id=d["msg_id"], parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Poll Job Error: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stop conversation."""
    await update.message.reply_text("Operasi dibatalkan.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AWAITING_ACCESS_CODE: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_access_code)],
            DASHBOARD: [CallbackQueryHandler(menu_callback)],
            SELECTING_MODEL: [CallbackQueryHandler(select_model)],
            SELECTING_DURATION: [CallbackQueryHandler(select_duration)],
            AWAITING_MEDIA: [MessageHandler(filters.PHOTO, handle_media_prompt)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    
    print("🤖 UniverseAI Bot is ready!")
    application.run_polling()

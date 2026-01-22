import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from supabase import create_client, Client

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State for ConversationHandler
AWAITING_ACCESS_CODE = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a message when the command /start is issued."""
    chat_id = update.effective_chat.id
    
    # Check if user is already logged in
    res = supabase.table("users").select("*").eq("telegram_id", str(chat_id)).execute()
    
    if res.data:
        user = res.data[0]
        if user.get("active_platform") == "telegram":
            await update.message.reply_text(
                f"Selamat datang kembali! Sesi Anda aktif.\n"
                f"Kirim pesan teks apa saja untuk dijadikan prompt video."
            )
            return ConversationHandler.END

    await update.message.reply_text(
        "Selamat datang di UniverseAI Video Generator Bot! 🤖\n\n"
        "Silakan masukkan 'Kode Akses' Anda untuk memulai."
    )
    return AWAITING_ACCESS_CODE

async def handle_access_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates the access code and links the Telegram account."""
    access_code = update.message.text.strip().upper()
    chat_id = update.effective_chat.id

    try:
        # Validate code in Supabase
        res = supabase.table("users").select("*").eq("code", access_code).execute()
        
        if not res.data:
            await update.message.reply_text("Kode akses tidak ditemukan. Silakan coba lagi atau hubungi admin.")
            return AWAITING_ACCESS_CODE
            
        user = res.data[0]
        
        # Update user session
        # active_platform='telegram' and save telegram_id
        # This effectively "kicks" the web session if the web app checks active_platform
        update_res = supabase.table("users").update({
            "active_platform": "telegram",
            "telegram_id": str(chat_id)
        }).eq("id", user["id"]).execute()
        
        if update_res.data:
            await update.message.reply_text(
                f"Login berhasil! Selamat datang, {user.get('code')}.\n"
                f"Sesi Web Anda telah diputus.\n\n"
                f"Sekarang Anda bisa mengirim 'Prompt' berupa pesan teks untuk membuat video."
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("Terjadi kesalahan saat mengupdate sesi. Silakan coba lagi.")
            return AWAITING_ACCESS_CODE

    except Exception as e:
        logger.error(f"Error validating access code: {e}")
        await update.message.reply_text("Terjadi kesalahan sistem. Silakan coba lagi nanti.")
        return AWAITING_ACCESS_CODE

async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles prompt text and inserts it into the tasks table."""
    chat_id = update.effective_chat.id
    prompt_text = update.message.text.strip()

    # Check if user is logged in
    res = supabase.table("users").select("*").eq("telegram_id", str(chat_id)).execute()
    
    if not res.data or res.data[0].get("active_platform") != "telegram":
        await update.message.reply_text("Anda belum login atau sesi Anda telah berakhir. Silakan kirim /start.")
        return

    user = res.data[0]

    try:
        # Insert into tasks table
        task_data = {
            "user_id": user["id"],
            "prompt": prompt_text,
            "status": "pending",
            "source": "telegram",
            "telegram_chat_id": str(chat_id)
        }
        
        insert_res = supabase.table("tasks").insert(task_data).execute()
        
        if insert_res.data:
            await update.message.reply_text(
                f"✅ Prompt diterima!\n"
                f"Prompt: \"{prompt_text}\"\n"
                f"Video Anda sedang masuk antrian. Mohon tunggu informasi selanjutnya."
            )
        else:
            await update.message.reply_text("Gagal membuat tugas. Silakan coba lagi.")

    except Exception as e:
        logger.error(f"Error inserting task: {e}")
        await update.message.reply_text("Terjadi kesalahan saat memproses prompt Anda.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Operasi dibatalkan.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

if __name__ == "__main__":
    if not all([TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
        print("Error: TELEGRAM_BOT_TOKEN, SUPABASE_URL, or SUPABASE_KEY is missing in .env")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Conversation handler for login
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AWAITING_ACCESS_CODE: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_access_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handlers
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_prompt))

    print("🤖 Python Telegram Bot is running...")
    application.run_polling()

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
from generation_helper import poll_status, finalize_generation
from queue_worker import worker_loop
from scripts.bot_cooldown_logic import check_cooldown, update_user_cooldown

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
r2 = R2Helper()

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- States ---
(
    LOGIN_INPUT,        # Waiting for access code input
    API_KEY_INPUT,      # Waiting for Ultra user API key
    DASHBOARD,          # Main menu (Callback Query)
    SELECTING_MODEL,    # Choosing model
    SELECTING_DURATION, # Choosing duration
    CONFIRM_CREDIT,     # Confirming pro credit usage
    AWAITING_MEDIA,     # Waiting for image upload
    SELECTING_RATIO,    # Choosing aspect ratio
) = range(8)

# --- Helpers ---

def get_user(chat_id):
    """Fetch user by telegram_id and verify active session."""
    try:
        res = supabase.table("users").select("*").eq("telegram_id", str(chat_id)).execute()
        if res.data:
            user = res.data[0]
            # Single Session Check: strict enforcement
            if user.get("active_platform") != 'telegram':
                return None 
            return user
        return None
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None

def get_active_models():
    """Fetch models active for telegram."""
    try:
        res = supabase.table("ai_models").select("*").eq("is_active_telegram", True).order("sort_order").execute()
        return res.data if res.data else []
    except:
        return []

def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    """Helper to build menu grid."""
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return InlineKeyboardMarkup(menu)

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/start entry point."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Check if already logged in and session is valid
    db_user = get_user(chat_id)
    if db_user:
        return await show_dashboard(update, context, db_user)

    # 1. Alur Awal (Login System)
    text = (
        "👋 **Selamat datang di UniverseAI.id**\n\n"
        "Silakan masukkan **Kode Akses** Anda untuk memulai:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔑 Masukkan Kode Akses", callback_data="btn_input_code")],
        [InlineKeyboardButton("🌐 Web Resmi", url="https://universeai.id")],
        [InlineKeyboardButton("📞 Hubungi Admin", url="https://wa.me/6285157306565")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        # Coming from "Back" button or similar callback
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    return LOGIN_INPUT

async def button_login_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the 'Masukkan Kode Akses' button."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "btn_input_code":
        await query.edit_message_text(
            "🔑 **Login Akses**\n\nSilakan ketik dan kirimkan **Kode Akses** Anda (Format: XXXX-XXXX-...)",
            parse_mode='Markdown'
        )
        return LOGIN_INPUT
        
    return LOGIN_INPUT

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate access code and handle Tier logic."""
    code = update.message.text.strip().upper()
    chat_id = update.effective_chat.id
    
    status_msg = await update.message.reply_text("🔄 Memverifikasi kode...")
    
    try:
        # 1. Verify Code
        res = supabase.table("users").select("*").eq("code", code).execute()
        if not res.data:
            await status_msg.edit_text("❌ **Kode Tidak Dikenal**\nPastikan Anda memasukkan kode dengan benar.")
            return LOGIN_INPUT
            
        user = res.data[0]
        user_tier = user.get('type', 'try').lower() # try, pro, ultra, unlimited
        
        # 2. Logic Tier 'Try' -> Kick
        if user_tier == 'try':
            await status_msg.edit_text(
                "🚫 **Akses Ditolak**\n\n"
                "Maaf, tier **TRY** hanya dapat digunakan melalui Website.\n"
                "Silakan upgrade ke PRO/Unlimited untuk akses Bot Telegram.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Buka Website", url="https://universeai.id")]])
            )
            return ConversationHandler.END # End session
            
        # 3. Update Session (Force Login)
        supabase.table("users").update({
            "active_platform": "telegram",
            "telegram_id": str(chat_id),
            "last_login_at": "now()"
        }).eq("id", user['id']).execute()
        
        # 4. Logic Tier 'Ultra' -> Minta Base API Key
        # If user is ultra, we check if they have custom key. If not, force input.
        if user_tier == 'ultra':
            # Check if key exists (optional optimization, but user logic says 'Setelah login, minta...')
            # Let's check first, maybe they already set it? 
            # Request says "Setelah login, minta user...". Let's assume we ensure it's there.
            if not user.get('custom_api_key'):
                await status_msg.edit_text(
                    "💎 **Welcome Ultra User!**\n\n"
                    "🔑 Anda belum memasukkan **API Key Freepik**.\n"
                    "API Key wajib untuk melanjutkan akses BYOK (Bring Your Own Key).\n\n"
                    "Silakan ketik API Key Anda:",
                    parse_mode='Markdown'
                )
                return API_KEY_INPUT
        
        await status_msg.delete()
        await update.message.reply_text("✅ **Login Berhasil!**")
        return await show_dashboard(update, context, user)
        
    except Exception as e:
        logger.error(f"Login Err: {e}")
        await status_msg.edit_text("⚠️ Terjadi kesalahan server.")
        return LOGIN_INPUT

async def handle_ultra_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Freepik API Key for Ultra users."""
    api_key = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # Update DB
    try:
        supabase.table("users").update({"custom_api_key": api_key}).eq("telegram_id", str(chat_id)).execute()
        await update.message.reply_text("✅ **API Key Disimpan!**")
        
        # Retrieve updated user and go to dashboard
        user = get_user(chat_id)
        return await show_dashboard(update, context, user)
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal menyimpan API Key: {e}")
        return API_KEY_INPUT

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None) -> int:
    """Main Dashboard with User Stats."""
    chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat.id
    if not user:
        user = get_user(chat_id)
        if not user:
            # Session invalid
            msg = "⚠️ Sesi Anda telah berakhir atau akun sedang digunakan di perangkat lain."
            if update.callback_query:
                await update.callback_query.message.reply_text(msg)
            else:
                await update.message.reply_text(msg)
            return await start(update, context)

    # Format Stats
    credits = user.get('credits', 0)
    tier = user.get('type', 'Unknown').upper()
    name = user.get('name', user.get('code')) # Fallback to code if name missing
    
    # Format Expired At
    expired_at = user.get("expired_at", "-")
    if expired_at and expired_at != "-":
        try:
            # Handle ISO string from Supabase
            dt = datetime.fromisoformat(str(expired_at).replace('Z', '+00:00'))
            expired_at = dt.strftime("%d %b %Y")
        except:
            pass

    text = (
        f"🤖 **UniverseAI Dashboard**\n"
        f"─────────────────\n"
        f"👤 **Nama:** {name}\n"
        f"📅 **Masa Aktif:** {expired_at}\n"
        f"💎 **Tier:** {tier}\n"
    )
    
    if tier == 'PRO':
        text += f"🪙 **Sisa Kredit:** {credits} Cr\n"
    
    text += f"─────────────────\n"
    text += "Silakan pilih menu:"

    keyboard = [
        [InlineKeyboardButton("🎬 Buat Video Baru", callback_data="menu_create")],
        [InlineKeyboardButton("💎 Cek Saldo", callback_data="menu_check_balance"), 
         InlineKeyboardButton("❓ Bantuan", callback_data="menu_help")],
        [InlineKeyboardButton("🔴 Keluar dari Bot", callback_data="menu_logout")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or Edit
    if update.callback_query:
        await update.callback_query.answer()
        # If message allows edit (text content), edit it. Else send new.
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    return DASHBOARD

async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Dashboard menu interactions."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    chat_id = query.message.chat.id
    user = get_user(chat_id)
    if not user:
        await query.message.reply_text("⚠️ Session expired.")
        return await start(update, context)

    if data == "menu_create":
        # Check active models
        models = get_active_models()
        if not models:
            await query.edit_message_text(
                "⚠️ Belum ada model AI yang tersedia saat ini.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data="back_to_dash")]])
            )
            return DASHBOARD
            
        # Build Model Grid with Dynamic Pricing
        buttons = []
        user_type = user.get('type', 'try').lower()
        for m in models:
            # Strict DB Pricing with Legacy Fallback
            # If cost_pro_5s is missing, try cost_pro, then credit_cost (legacy default from existing dashboard)
            base_cost = m.get('credit_cost') or 0
            cost_5s = m.get('cost_pro_5s') or m.get('cost_pro') or base_cost or 0
            cost_10s = m.get('cost_pro_10s') or m.get('cost_pro') or (base_cost * 2) or 0
            is_free_5s = m.get('is_free_pro_5s', False)
            
            # Format: [🎬 Kling 2.1 🪙 4 - 8 Cr] or [🎬 Kling 2.1 🪙 Gratis - 10 Cr]
            if user_type == 'pro':
                if is_free_5s:
                     label = f"🎬 {m['display_name']} 🪙 Gratis - {cost_10s} Cr"
                else:
                     label = f"🎬 {m['display_name']} 🪙 {cost_5s} - {cost_10s} Cr"
            else:
                # Ultra/Unlimited users - show model name only
                label = f"🎬 {m['display_name']}"
            
            buttons.append(InlineKeyboardButton(label, callback_data=f"model_{m['model_id']}"))
            
        footer = [InlineKeyboardButton("⬅️ Kembali", callback_data="back_to_dash")]
        reply_markup = build_menu(buttons, n_cols=2, footer_buttons=footer)
        
        await query.edit_message_text(
            "🎨 **Pilih Model AI**\nSilakan pilih model yang ingin digunakan:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return SELECTING_MODEL
        
    elif data == "menu_check_balance":
        # Show balance details
        credits = user.get('credits', 0)
        tier = user.get('type', 'Unknown').upper()
        
        balance_text = (
            f"💎 **Cek Saldo**\n"
            f"─────────────────\n"
            f"📊 **Tier:** {tier}\n"
        )
        
        if tier == 'PRO':
            balance_text += f"🪙 **Saldo Kredit:** {credits} Cr\n"
        elif tier in ['ULTRA', 'UNLIMITED']:
            balance_text += f"♾️ **Akses:** Unlimited\n"
        else:
            balance_text += f"🪙 **Kredit:** {credits} Cr\n"
        
        balance_text += "─────────────────"
        
        await query.edit_message_text(
            balance_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Kembali", callback_data="back_to_dash")]
            ]),
            parse_mode='Markdown'
        )
        return DASHBOARD
        
    elif data == "back_to_dash":
        return await show_dashboard(update, context, user)

    elif data == "menu_logout":
        # Logika Tombol Keluar
        try:
            supabase.table("users").update({
                "active_platform": "web",
                "telegram_id": None
            }).eq("id", user['id']).execute()
            
            await query.message.delete()
            await query.message.reply_text("✅ **Anda telah keluar.**\nTerima kasih telah menggunakan layanan kami.")
            
            # Kembali ke instruksi /start
            return await start(update, context)
            
        except Exception as e:
            logger.error(f"Logout Error: {e}")
            await query.message.reply_text("❌ Gagal logout.")
            return DASHBOARD
        
    return DASHBOARD

async def select_model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Model Selection."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_to_dash":
        user = get_user(query.message.chat.id)
        return await show_dashboard(update, context, user)
    
    model_id = data.replace("model_", "")
    context.user_data['selected_model_id'] = model_id
    
    # Fetch model info for dynamic pricing
    chat_id = query.message.chat.id
    user = get_user(chat_id)
    user_type = user.get('type', 'try').lower() if user else 'try'
    
    try:
        model_res = supabase.table("ai_models").select("*").eq("model_id", model_id).execute()
        model_info = model_res.data[0] if model_res.data else {}
        context.user_data['selected_model_info'] = model_info
    except:
        model_info = {}
        context.user_data['selected_model_info'] = {}
    
    # Get pricing from DB
    cost_5s = model_info.get('cost_pro_5s', model_info.get('cost_pro', 0)) or 0
    cost_10s = model_info.get('cost_pro_10s', model_info.get('cost_pro', 0)) or 0
    is_free_5s = model_info.get('is_free_pro_5s', False) or user_type in ['ultra', 'unlimited']
    is_unlimited = user_type in ['ultra', 'unlimited']
    
    # Build duration buttons with dynamic labels
    buttons = []
    if is_unlimited:
        # Ultra/Unlimited - no credit display
        buttons.append(InlineKeyboardButton("⏱️ 5 Detik", callback_data="dur_5"))
        buttons.append(InlineKeyboardButton("⏱️ 10 Detik", callback_data="dur_10"))
    else:
        # Pro users - show pricing
        if is_free_5s:
            buttons.append(InlineKeyboardButton("⏱️ 5 Detik (Gratis)", callback_data="dur_5"))
        else:
            buttons.append(InlineKeyboardButton(f"⏱️ 5 Detik (🪙 {cost_5s} Credit)", callback_data="dur_5"))
        buttons.append(InlineKeyboardButton(f"⏱️ 10 Detik (🪙 {cost_10s} Credit)", callback_data="dur_10"))
    
    footer = [InlineKeyboardButton("⬅️ Kembali", callback_data="back_to_models")]
    display_name = model_info.get('display_name', model_id)
    
    await query.edit_message_text(
        f"⏱️ **Pilih Durasi Video**\nModel: `{display_name}`",
        reply_markup=build_menu(buttons, n_cols=1, footer_buttons=footer),
        parse_mode='Markdown'
    )
    return SELECTING_DURATION

async def select_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Duration Selection and Cost Confirmation."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_to_models":
        # Go back to logic in dashboard_callback -> menu_create
        # We simulate it by creating a fake update or calling the function logic?
        # Easier to just redirect user to dashboard click logic manually or re-render
        return await dashboard_callback(update, context) # This might need tweaking, let's keep it simple:
        # Actually dashboard_callback expects specific data strings.
        # Let's just re-render model list.
        # Reuse code block from dashboard_callback?
        # Better: just set data="menu_create" and call
        query.data = "menu_create"
        return await dashboard_callback(update, context)

    duration = data.replace("dur_", "")
    context.user_data['selected_duration'] = duration
    
    chat_id = query.message.chat.id
    user = get_user(chat_id)
    model_id = context.user_data.get('selected_model_id')
    
    # Strict DB Pricing - No Hardcoded Defaults
    # Fetch FRESH model info to ensure real-time sync with Admin Dashboard
    try:
        m_res = supabase.table("ai_models").select("*").eq("model_id", model_id).execute()
        model_info = m_res.data[0]
    except:
        await query.edit_message_text("❌ Error fetching model info.")
        return DASHBOARD

    user_type = user.get('type', 'try').lower()
    is_free_5s = model_info.get('is_free_pro_5s', False)
    
    # Pricing with Fallback
    base_cost = model_info.get('credit_cost') or 0
    cost_5s = int(model_info.get('cost_pro_5s') or model_info.get('cost_pro') or base_cost or 0)
    cost_10s = int(model_info.get('cost_pro_10s') or model_info.get('cost_pro') or (base_cost * 2) or 0)
    
    # Determine cost based on selected duration
    if duration == '5':
        cost = 0 if is_free_5s else cost_5s
    else:  # 10 seconds or others
        cost = cost_10s
    
    context.user_data['calculated_cost'] = cost
    
    # Skip confirmation if cost is 0 (Free) or Unlimited User
    if user_type in ['ultra', 'unlimited'] or cost == 0:
        return await ask_aspect_ratio(query, context)
    
    # Condition: Pro User AND cost > 0
    if user_type == 'pro' and cost > 0:
        text = (
            f"⚠️ **Konfirmasi Kredit**\n\n"
            f"Durasi **{duration} detik** memerlukan **{cost} Kredit**.\n"
            f"Sisa Kredit Anda: **{user.get('credits', 0)}**\n\n"
            f"Lanjutkan?"
        )
        buttons = [
            InlineKeyboardButton("✅ Setuju", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Batal", callback_data="confirm_no")
        ]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([buttons]), parse_mode='Markdown')
        except:
             # Fallback if message content same (though unlikely with dynamic cost)
             pass
        return CONFIRM_CREDIT

    # Proceed to Ratio Selection
    return await ask_aspect_ratio(query, context)

async def handle_credit_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "confirm_no":
        await query.edit_message_text("❌ Dibatalkan.")
        user = get_user(query.message.chat.id)
        return await show_dashboard(update, context, user)
        
    if data == "confirm_yes":
        # Check balance again
        user = get_user(query.message.chat.id)
        cost = context.user_data.get('calculated_cost', 0)
        
        if user.get('credits', 0) < cost:
            await query.edit_message_text(
                "🚫 **Kredit Tidak Cukup**\nSilakan topup melalui website kami.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Topup", url="https://universeai.id")]])
            )
            return DASHBOARD
            
        # Proceed
        return await ask_aspect_ratio(query, context)

async def ask_aspect_ratio(update_or_query, context):
    """Step 3: Ask for Aspect Ratio"""
    # Helper to send message whether from callback or cleanup
    message = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    
    buttons = [
        [InlineKeyboardButton("16:9 (Landscape)", callback_data="ratio_16:9")],
        [InlineKeyboardButton("9:16 (Portrait)", callback_data="ratio_9:16")],
        [InlineKeyboardButton("1:1 (Square)", callback_data="ratio_1:1")],
    ]
    
    text = "📐 **Pilih Aspect Ratio**\n\nSilakan pilih rasio video yang diinginkan:"
    
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
        
    return SELECTING_RATIO
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "confirm_no":
        await query.edit_message_text("❌ Dibatalkan.")
        user = get_user(query.message.chat.id)
        return await show_dashboard(update, context, user)
        
    if data == "confirm_yes":
        # Check balance again
        user = get_user(query.message.chat.id)
        cost = context.user_data.get('calculated_cost', 0)
        
        if user.get('credits', 0) < cost:
            await query.edit_message_text(
                "🚫 **Kredit Tidak Cukup**\nSilakan topup melalui website kami.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Topup", url="https://universeai.id")]])
            )
            return DASHBOARD # Or end
            
        # Proceed
        # Proceed
        return await ask_aspect_ratio(query, context)

async def request_media(update_or_query, context):
    """Step 4: Ask user to upload photo."""
    # Can be called from callback or direct
    if hasattr(update_or_query, 'message'):
        msg_obj = update_or_query.message
        # If callback
        if hasattr(update_or_query, 'edit_message_text'):
             func = update_or_query.edit_message_text
        else:
             func = msg_obj.reply_text
    else:
        # Should not happen typically unless raw message passed
        msg_obj = update_or_query
        func = msg_obj.reply_text

    await func(
        f"📸 **Upload Foto**\n\n"
        f"Silakan kirimkan **1 Foto** yang ingin dianimasikan.\n"
        f"Jangan lupa tambahkan **Caption** sebagai prompt instruksi visual.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Batal", callback_data="cancel_upload")]])
    )
    return AWAITING_MEDIA

async def handle_ratio_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Aspect Ratio Selection -> Ask for Media."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    ratio = data.replace("ratio_", "") if data.startswith("ratio_") else "16:9"
    context.user_data['selected_ratio'] = ratio
    
    # Next: Request Media
    return await request_media(query, context)

async def handle_media_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process Media and Prompt, Create Task."""
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    
    if not user:
        await update.message.reply_text("Session Expired. /start")
        return ConversationHandler.END

    # ====== LOCK PRO CHECK (Anti-Spam) ======
    user_type = user.get('type', 'try').lower()
    model_id = context.user_data.get('selected_model_id')

    # ====== COOLDOWN CHECK ======
    if user_type in ['pro', 'unlimited', 'ultra']:
        is_allowed, msg = await check_cooldown(
            supabase_client=supabase,
            user_id=user['id'],
            user_type=user_type,
            model_name=model_id
        )

        if not is_allowed:
            await update.message.reply_text(msg, parse_mode='Markdown')
            return await show_dashboard(update, context, user)
    # ====== END COOLDOWN CHECK ======

    # ====== LOCK PRO CHECK (Anti-Spam) ======
    if user_type == 'pro':
        # Check for active processing tasks
        try:
            processing_res = supabase.table("generations") \
                .select("id", count="exact") \
                .eq("user_id", user['id']) \
                .eq("status", "processing") \
                .execute()
            
            processing_count = processing_res.count if processing_res.count else 0
            
            if processing_count > 0:
                await update.message.reply_text(
                    "⏳ **Tunggu dulu bosque!**\n\n"
                    "Masih ada video yang sedang diproses.\n"
                    "Tunggu sampai video selesai dibuat ya! 🎬",
                    parse_mode='Markdown'
                )
                return await show_dashboard(update, context, user)
        except Exception as e:
            logger.warning(f"Lock Pro check failed: {e}")
    # ====== END LOCK PRO ======

    if not update.message.photo:
        await update.message.reply_text("⚠️ Harap kirimkan format **Foto**.")
        return AWAITING_MEDIA
        
    photo = update.message.photo[-1]
    prompt = update.message.caption or ""
    
    if not prompt:
        await update.message.reply_text("⚠️ **Caption** (prompt) wajib diisi! Silakan kirim ulang foto + caption.")
        return AWAITING_MEDIA

    # Prepare Task
    msg = await update.message.reply_text("🚀 Menyiapkan tugas...")
    
    try:
        # Upload Image
        await msg.edit_text("⏳ Mengunggah media...")
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        
        chat_id = update.effective_chat.id
        file_name = f"tele_{chat_id}_{int(datetime.now().timestamp())}.jpg"
        image_url = r2.upload_bytes(photo_bytes, file_name, content_type='image/jpeg')
        
        if not image_url:
            logger.error(f"[TELEGRAM] Failed to upload image for chat_id {chat_id}")
            await msg.edit_text("❌ Gagal upload media.")
            return await show_dashboard(update, context, user)
            
        logger.info(f"[TELEGRAM] Image uploaded to R2: {image_url}")

        # Retrieve context data
        model_id = context.user_data.get('selected_model_id')
        duration = context.user_data.get('selected_duration')
        ratio = context.user_data.get('selected_ratio', '16:9')

        if not model_id or not duration:
            logger.error(f"[TELEGRAM] Missing session data (Model: {model_id}, Dur: {duration})")
            await msg.edit_text("❌ Data sesi hilang. Silakan ulangi dari menu utama.")
            return await show_dashboard(update, context, user)

        # Prepare final payload for generations table (serving as queue)
        gen_data = {
            "user_id": user["id"],
            "prompt": prompt,
            "status": "pending",
            "source": "telegram",
            "thumbnail_url": image_url, # file_url in tasks -> thumbnail_url in generations
            "telegram_chat_id": str(chat_id),
            "model_name": model_id,
            "aspect_ratio": ratio,
            "options": {
                "duration": duration, 
                "msg_id": msg.message_id,
                "credits_used": context.user_data.get('calculated_cost', 0)
            },
            "created_at": "now()"
        }
        
        # Attempt Insert into generations
        supabase.table("generations").insert(gen_data).execute()
        logger.info(f"[TELEGRAM] Task inserted into generations for user {user['id']} (Model: {model_id})")

        # Update Cooldown Count
        await update_user_cooldown(supabase, user['id'], model_id)
        
        # Update message to "Queued" state, this message will be picked up by worker
        await msg.edit_text(
            f"⏳ **Antrian...**\n"
            f"Posisi: 1\n"
            f"Model: {model_id}\n"
            f"Mohon tunggu sebentar...",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Task Creation Error: {e}")
        err_msg = str(e)
        if "aspect_ratio" in err_msg and "column" in err_msg:
             await msg.edit_text(f"❌ **Error Database:** Kolom 'aspect_ratio' tidak ditemukan di tabel tasks. Mohon lapor admin.")
        elif "options" in err_msg and "column" in err_msg:
             await msg.edit_text(f"❌ **Error Database:** Kolom 'options' tidak ditemukan di tabel tasks. Mohon lapor admin.")
        else:
             await msg.edit_text(f"❌ Gagal membuat tugas: {e}")
        return await show_dashboard(update, context, user)

async def poll_status_job(context: ContextTypes.DEFAULT_TYPE):
    """Update loading visuals and handle final video."""
    job = context.job
    d = job.data
    
    elapsed = int((datetime.now() - d["start_time"]).total_seconds())
    # Visual Progress (Fake but satisfying)
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
            # R2 upload might take time, careful with job timeout? 
            # Ideally run in thread, but for now await is ok.
            video_name = f"gen_video_{d['gen_id']}.mp4"
            r2_video_url = r2.upload_from_url(video_url, video_name, content_type='video/mp4')
            
            finalize_generation(d["gen_id"], video_url, d["user_id"], r2_video_url)
            
            final_url = r2_video_url or video_url
            
            # ====== POST-GENERATE SUMMARY ======
            # Fetch credits_used from generation record and updated user balance
            credits_used = d.get("credits_used", 0)
            try:
                updated_user = supabase.table("users").select("credits, type").eq("id", d["user_id"]).execute()
                if updated_user.data:
                    new_credits = updated_user.data[0].get('credits', 0)
                    user_type = updated_user.data[0].get('type', '').lower()
                else:
                    new_credits = 0
                    user_type = ''
            except:
                new_credits = 0
                user_type = ''
            
            # Build caption with cost summary
            caption = (
                f"🎬 **Video UniverseAI**\n"
                f"Model: `{d['model_id']}`\n"
                f"Prompt: \"{d['prompt'][:50]}{'...' if len(d['prompt']) > 50 else ''}\"\n\n"
                f"─────────────────\n"
            )
            
            if user_type in ['ultra', 'unlimited']:
                caption += f"💰 **Biaya:** Gratis (Unlimited)\n"
            else:
                caption += f"💰 **Biaya:** {credits_used} 🪙\n"
                caption += f"💎 **Sisa Saldo:** {new_credits} 🪙\n"
            
            caption += "─────────────────"
            
            # Build buttons for post-generate actions
            post_buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Buat Video Lagi", callback_data="menu_create")],
                [InlineKeyboardButton("📥 Download File", callback_data=f"dl_{d['gen_id']}")]
            ])
            # ====== END POST-GENERATE ======
            
            # Send Final Video with Summary
            await context.bot.send_video(
                chat_id=d["chat_id"], 
                video=final_url, 
                caption=caption,
                parse_mode='Markdown',
                reply_markup=post_buttons
            )
            job.schedule_removal()
            return

        elif status == "failed":
            await context.bot.edit_message_text(f"❌ Gagal: {video_url}", chat_id=d["chat_id"], message_id=d["msg_id"])
            job.schedule_removal()
            return
            
        # Update progress visual
        # Only update every few checks to avoid rate limit?
        # PTB handles throttle automatically mostly, but good to be safe.
        await context.bot.edit_message_text(
            f"🎬 **Video sedang di-generate...**\n\n`[{bar}] {progress}%`\nWaktu berjalan: {elapsed} detik",
            chat_id=d["chat_id"], message_id=d["msg_id"], parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Poll Job Error: {e}")
        # Don't remove job, try again next tick unless critical

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generic cancel."""
    user = get_user(update.effective_chat.id if update.effective_chat else update.callback_query.message.chat.id)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("❌ Dibatalkan.")
    else:
        await update.message.reply_text("❌ Dibatalkan.")
        
    if user:
        return await show_dashboard(update, context, user)
    return ConversationHandler.END

async def download_video_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Download Video button click."""
    query = update.callback_query
    await query.answer() # Acknowledge the click immediately
    
    data = query.data
    try:
        gen_id = data.replace("dl_", "")
        
        # Fetch generation data to get URL
        res = supabase.table("generations").select("r2_url, video_url").eq("id", gen_id).execute()
        if not res.data:
            await query.message.reply_text("❌ Data video tidak ditemukan.")
            return

        gen_data = res.data[0]
        # output_url (R2) or thumbnail_url (as fallback? usually thumbnail is image)
        # Ideally we saved 'output_url' in finalize_generation. 
        # Check generation_helper.py: finalize_generation updates: 'output_url' -> r2_url
        video_url = gen_data.get('r2_url') or gen_data.get('video_url')
        
        if not video_url:
             await query.message.reply_text("❌ Link video belum tersedia.")
             return

        # Notify user (sending file takes bandwidth)
        msg = await query.message.reply_text("📥 **Mengunduh file...**\nMohon tunggu, sedang mengirim file ke chat Anda.", parse_mode='Markdown')
        
        # Send as Document
        await context.bot.send_document(
            chat_id=query.message.chat.id,
            document=video_url,
            filename=f"UniverseAI_Video_{gen_id}.mp4",
            caption=f"✅ Berikut file video Anda."
        )
        
        # Delete the "Downloading..." status message
        await msg.delete()

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await query.message.reply_text(f"❌ Gagal mengirim file: {e}")

# --- Main Setup ---

async def post_init(application):
    """Force logout all telegram users on startup."""
    logger.info("Executing Force Logout (Resetting active_platform)...")
    try:
        supabase.table("users").update({"active_platform": "web"}).eq("active_platform", "telegram").execute()
        logger.info("Force logout complete.")
    except Exception as e:
        logger.error(f"Post-init failed: {e}")
        
    # Start Background Worker
    # running on the same loop as the bot
    asyncio.create_task(worker_loop(application))
    logger.info("Background Worker Started via post_init.")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found.")
        exit(1)
        
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Attach Poll Job to Application for Worker access
    application.bot_data["poll_status_callback"] = poll_status_job
    
    # Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(download_video_file, pattern="^dl_"),
            CallbackQueryHandler(button_login_actions, pattern="^btn_input_code$")
        ],
        states={
            LOGIN_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login),
                CallbackQueryHandler(button_login_actions, pattern="^btn_input_code$")
            ],
            API_KEY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ultra_api_key)],
            DASHBOARD: [CallbackQueryHandler(dashboard_callback)],
            SELECTING_MODEL: [CallbackQueryHandler(select_model_callback)],
            SELECTING_DURATION: [CallbackQueryHandler(select_duration_callback)],
            CONFIRM_CREDIT: [CallbackQueryHandler(handle_credit_confirmation)],
            AWAITING_MEDIA: [
                MessageHandler(filters.PHOTO, handle_media_upload),
                CallbackQueryHandler(cancel_handler, pattern="^cancel_upload$")
            ],
            SELECTING_RATIO: [CallbackQueryHandler(handle_ratio_selection)]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel_handler)]
    )
    
    application.add_handler(conv_handler)
    
    print("🚀 UniverseAI Bot Started (Tier System Active)...")
    application.run_polling()

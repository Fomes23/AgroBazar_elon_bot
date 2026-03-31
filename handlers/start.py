from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

from database import Database
from my_utils import safe_send
import logging

logger = logging.getLogger(__name__)
# ====================== GLOBAL DATABASE ======================
# Har bir faylda alohida yaratmang! Bitta global db dan foydalaning.
db = Database()  # Bu yerda yaratish mumkin, lekin eng yaxshisi main.py dan import qilish


# ===============================
# MENU FUNKSIYASI
# ===============================
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🛒 E'lon berish"), KeyboardButton("💰 Mahsulot sotib olish")],
        [KeyboardButton("📄 Mening e'lonlarim"), KeyboardButton("❓ Yordam")]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Menyudan tanlang..."
    )

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text="🧺 *Agro Bazar botiga xush kelibsiz!* 🌾\n\n"
             "👉 *Boshlash uchun quyidagi menyudan tanlang:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ===============================
# /START HANDLER
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id

    db_user = await db.get_user(telegram_id)

    if db_user:
        await show_menu(update, context)
        return

    # Ro'yxatdan o'tmagan foydalanuvchi
    keyboard = [[KeyboardButton("📱 Raqamingizni ulashing", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text="👋 *Assalomu alaykum!* \n\n"
             "Ro‘yxatdan o‘tish uchun pastdagi 📱 tugmani bosib, "
             "telefon raqamingizni yuboring.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ===============================
# CONTACT HANDLER
# ===============================
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.contact:
        await safe_send(
            context.bot,
            chat_id=update.effective_chat.id,
            text="⚠️ Iltimos, pastdagi tugma orqali telefon raqamingizni yuboring."
        )
        return

    contact = update.message.contact
    user = update.effective_user
    telegram_id = user.id

    if contact.user_id and contact.user_id != telegram_id:
        await safe_send(
            context.bot,
            chat_id=update.effective_chat.id,
            text="⚠️ Iltimos, faqat o‘z raqamingizni yuboring!"
        )
        return

    # Foydalanuvchini bazaga qo'shish/yangilash
    await db.add_or_update_user(
        telegram_id=telegram_id,
        full_name=user.full_name or "",
        username=user.username or "",
        phone_user=contact.phone_number
    )

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text="✅ *Siz muvaffaqiyatli ro‘yxatdan o‘tdingiz!* 🎉\n\n"
             "Endi botdan to‘liq foydalanishingiz mumkin.",
        parse_mode="Markdown"
    )

    await show_menu(update, context)


# ===============================
# HANDLERLARNI RO‘YXATGA OLISH
# ===============================
def start_handlers(application):
    """Handlerlarni qo'shish"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.CONTACT & ~filters.COMMAND, contact_handler)
    )

    return application
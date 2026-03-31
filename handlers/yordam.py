from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes,MessageHandler, filters
from app import  CHANNEL_LINK,ADMIN_USERNAME


# CHANNEL_LINK = "https://t.me/YourChannelUsername"  # Kanal username
# ADMIN_USERNAME = "AdminUsername"                   # Admin username

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Inline tugmalar
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o'tish", url=CHANNEL_LINK)],
        [InlineKeyboardButton("👤 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])

    # Qisqa va tushunarli yordam matni
    help_text = (
        "🛒 Agro Bazar Bot – Tez Yo‘riqnoma\n\n"
        "1️⃣ Kanaldagi mahsulotlar\n"
        "🏷 Nomi, narxi, miqdori, joylashuvi va izohi\n"
        "📌 Sotib olmoqchi bo‘lsangiz, egasi bilan bog‘laning\n\n"
        "2️⃣ Bot orqali e’lon berish\n"
        "🛒 Nom, narx, miqdor, joylashuv, izoh va rasm qo‘shing\n"
        "✅ Tasdiqlangach, e’lon kanalga chiqadi\n\n"
        "3️⃣ Mening e’lonlarim\n"
        "📄 Qo‘shgan e’lonlaringizni ko‘ring\n"
        "⚠️ O‘chirish yoki “Sotildi” deb belgilash imkoniyati\n\n"
        "💡 Kanalga obuna bo‘ling – barcha imkoniyatlardan foydalaning!"
    )

    await update.message.reply_text(
        help_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

def yordam_handlers(application):
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^❓ Yordam$"), help_handler))
    return application

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, filters
from app import CHANNEL_LINK

# CHANNEL_LINK = "https://t.me/YourChannelUsername"  # o‘zingizning kanal

async def buy_handler(update, context):
    # Inline tugma bilan kanalga yuborish
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o‘tish", url=CHANNEL_LINK)]
    ])

    await update.message.reply_text(
        "🛒 Barcha mahsulotlarimiz kanalimizda joylangan.\n"
        "👇 Ko‘rish uchun quyidagi tugmani bosing:",
        reply_markup=keyboard
    )

def kanal_handlers(application):
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💰 Mahsulot sotib olish$"), buy_handler))
    return application
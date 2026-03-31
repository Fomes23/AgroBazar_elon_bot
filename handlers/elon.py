from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler,
    filters, CommandHandler
)

from database import Database
from my_utils import safe_send
import logging

logger = logging.getLogger(__name__)
db = Database()

# Conversation states
PRODUCT, PRICE, AMOUNT, LOCATION, PHONE, DESCRIPTION, PHOTOS, REVIEW = range(8)

# =========================
# HELPER KEYBOARDS
# =========================
def inline_nav():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❎ Bekor qilish", callback_data="cancel")]])

def photo_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Yana rasm qo‘shish", callback_data="add_more")],
        [InlineKeyboardButton("✅ Yetarli, davom ettirish", callback_data="finish_photos")],
        [InlineKeyboardButton("❎ Bekor qilish", callback_data="cancel")]
    ])

def review_keyboard():
    keyboard = [
        [InlineKeyboardButton("✏️ Nom", callback_data="edit_product"),
         InlineKeyboardButton("✏️ Narx", callback_data="edit_price")],
        [InlineKeyboardButton("✏️ Miqdor", callback_data="edit_amount"),
         InlineKeyboardButton("✏️ Manzil", callback_data="edit_location")],
        [InlineKeyboardButton("✏️ Telefon", callback_data="edit_phone"),
         InlineKeyboardButton("✏️ Izoh", callback_data="edit_desc")],
        [InlineKeyboardButton("✅ Tasdiqlash va yuborish", callback_data="submit_ad"),
         InlineKeyboardButton("❎ Bekor qilish", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# =========================
# E'LON BERISHNI BOSHLASH
# =========================
async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['photos'] = []

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text="📦 Mahsulotingiz nomini kiriting:\n"
             "(Masalan: Olma, Sabzi, Bug‘doy, Chorva va h.k.)",
        reply_markup=inline_nav()
    )
    return PRODUCT

# =========================
# MA'LUMOTLarni olish
# =========================
async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product'] = update.message.text.strip().title()
    return await next_step(update, context, PRICE, "💰 Mahsulot narxini kiriting (faqat raqam, masalan: 15000):")

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_str = update.message.text.replace(" ", "").replace(",", ".")
        price = float(price_str)
        if price <= 0:
            raise ValueError
        context.user_data['price'] = price
    except ValueError:
        await safe_send(context.bot, update.effective_chat.id,
                        "⚠️ Narxni faqat musbat son ko‘rinishida kiriting!")
        return PRICE

    return await next_step(update, context, AMOUNT, "⚖️ Miqdorini kiriting (masalan: 500 kg, 2 tonna, 10 dona):")

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['amount'] = update.message.text.strip()
    return await next_step(update, context, LOCATION, "📍 Manzilni kiriting (masalan: Toshkent, Yunusobod, ...):")

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text.strip().title()
    return await next_step(update, context, PHONE, "📞 Telefon raqamingizni kiriting (+998... yoki 90...):")

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text.strip()
    return await next_step(update, context, DESCRIPTION,
                           "📝 Qo‘shimcha izoh kiriting (yoki /skip):")

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['description'] = "" if text.lower() in ["/skip", "skip"] else text

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text="📸 Mahsulot rasmlarini yuboring (kamida 1 ta, maksimal 3 ta):",
        reply_markup=inline_nav()
    )
    return PHOTOS

async def next_step(update: Update, context: ContextTypes.DEFAULT_TYPE, next_state: int, text: str):
    if context.user_data.get('is_editing'):
        await safe_send(context.bot, update.effective_chat.id, "✅ Ma'lumot yangilandi!")
        del context.user_data['is_editing']
        await review_ad(update, context)
        return REVIEW

    await safe_send(context.bot, update.effective_chat.id, text, reply_markup=inline_nav())
    return next_state

# =========================
# RASMLARNI QABUL QILISH
# =========================
async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.setdefault('photos', [])
    # Rasmlar xabarlarining ID-larini saqlash uchun ro'yxat ochamiz
    photo_msg_ids = context.user_data.setdefault('photo_message_ids', [])

    if len(photos) >= 3:
        # Maksimal miqdorga yetganda, foydalanuvchi yuborgan ortiqcha xabarni ham o'chirish uchun ID-sini saqlaymiz
        photo_msg_ids.append(update.message.message_id)

        await safe_send(context.bot, update.effective_chat.id,
                        "⚠️ Maksimal 3 ta rasm qo‘shishingiz mumkin!",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Yetarli, davom ettirish", callback_data="finish_photos")],
                            [InlineKeyboardButton("❎ Bekor qilish", callback_data="cancel")]
                        ]))
        return PHOTOS

    if update.message.photo:
        # 1. Rasmni o'zini saqlash (bazaga yuborish uchun)
        photo_id = update.message.photo[-1].file_id
        photos.append(photo_id)

        # 2. Rasm kelgan xabar ID-sini saqlash (keyinchalik o'chirish uchun)
        photo_msg_ids.append(update.message.message_id)

    # Botning "Rasm qo'shildi" degan javob xabarini ham saqlab qo'ysak bo'ladi (uni ham o'chirish uchun)
    sent_msg = await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text=f"✅ Rasm qo‘shildi! Jami: {len(photos)} ta. Yana rasm yuborishingiz yoki davom etishingiz mumkin.",
        reply_markup=photo_buttons())

    if sent_msg:
        photo_msg_ids.append(sent_msg.message_id)

    return PHOTOS

async def photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_more":
        await safe_send(context.bot, query.message.chat_id, "📸 Yana rasm yuboring:")
        return PHOTOS

    elif query.data == "finish_photos":
        if not context.user_data.get('photos'):
            await query.answer("⚠️ Kamida 1 ta rasm yuborishingiz kerak!", show_alert=True)
            return PHOTOS

        await review_ad(update, context)
        return REVIEW

    elif query.data == "cancel":
        context.user_data.clear()
        await query.message.edit_text("🚫 E'lon berish bekor qilindi.")
        return ConversationHandler.END

# =========================
# REVIEW VA TASDIQLASH
# =========================
async def review_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    text = f"""🧾 *E'lonni tasdiqlang*

📦 Mahsulot: {data.get('product', '—')}
💰 Narx: {data.get('price', '—')} so‘m
⚖️ Miqdor: {data.get('amount', '—')}
📍 Manzil: {data.get('location', '—')}
📞 Telefon: {data.get('phone', '—')}
📝 Izoh: {data.get('description') or 'Yo‘q'}
📸 Rasmlar: {len(data.get('photos', []))} ta"""

    try:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.delete()
    except:
        pass

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode="Markdown",
        reply_markup=review_keyboard()
    )
    return REVIEW

async def edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        context.user_data.clear()
        await query.message.edit_text("🚫 E'lon berish bekor qilindi.")
        return ConversationHandler.END

    if query.data == "submit_ad":
        return await submit_ad(update, context)

    field_map = {
        "edit_product": (PRODUCT, "📦 Yangi nom kiriting:"),
        "edit_price": (PRICE, "💰 Yangi narx kiriting:"),
        "edit_amount": (AMOUNT, "⚖️ Yangi miqdor kiriting:"),
        "edit_location": (LOCATION, "📍 Yangi manzil kiriting:"),
        "edit_phone": (PHONE, "📞 Yangi telefon raqam kiriting:"),
        "edit_desc": (DESCRIPTION, "📝 Yangi izoh kiriting (yoki /skip):"),
    }

    if query.data in field_map:
        state, text = field_map[query.data]
        context.user_data['is_editing'] = True
        await safe_send(context.bot, query.message.chat_id, text, reply_markup=inline_nav())
        return state


async def submit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = context.user_data
    user_id_tg = query.from_user.id

    try:
        # 1. Rasmlar xabarlarining ID larini olib qo'yamiz (o'chirish uchun)
        photo_messages = data.get('photo_message_ids', [])

        user_id = await db.get_user_id(user_id_tg)
        await db.add_pending_ad(
            user_id=user_id,
            product=data.get('product'),
            price=float(data.get('price')),
            amount=data.get('amount'),
            location=data.get('location'),
            phone=data.get('phone'),
            description=data.get('description', ''),
            photos=data.get('photos', [])
        )

        # 2. "Tasdiqlash" tugmasi bor xabarni o'chirish
        if query.message:
            await query.message.delete()

        # 3. Foydalanuvchi yuborgan rasmlarni chatdan o'chirish (agar ID larni saqlagan bo'lsangiz)
        photo_messages = data.get('photo_message_ids', [])
        for msg_id in photo_messages:
            try:
                await context.bot.delete_message(chat_id=query.from_user.id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Xabarni o'chirishda xato: {e}")

        await safe_send(context.bot, user_id_tg, "✅ E’loningiz muvaffaqiyatli yuborildi! Admin tekshiruvidan so`ng kanalga chiqariladi.")

    except Exception as e:
        logger.error(f"Submit error: {e}")
        await safe_send(context.bot, user_id_tg, "⚠️ Xatolik yuz berdi.")
    finally:
        # Ma'lumotlarni faqat muvaffaqiyatli yakunlanganda yoki xatodan keyin tozalaymiz
        context.user_data.clear()

    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await safe_send(context.bot, update.effective_chat.id, "🚫 E'lon berish bekor qilindi.")
    return ConversationHandler.END

# =========================
# CONVERSATION HANDLER
# =========================
def elon_handlers(application):
    # Bekor qilish callbacki uchun umumiy handler
    cancel_callback = CallbackQueryHandler(edit_callback, pattern="^cancel$")

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🛒 E'?lon berish$"), sell_start)
        ],
        states={
            # Har bir statega cancel callback qo'shildi
            PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product), cancel_callback],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price), cancel_callback],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount), cancel_callback],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location), cancel_callback],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone), cancel_callback],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc), cancel_callback],
            PHOTOS: [
                MessageHandler(filters.PHOTO, get_photos),
                CallbackQueryHandler(photo_callback, pattern="^(add_more|finish_photos|cancel)$")
            ],
            REVIEW: [CallbackQueryHandler(edit_callback)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            cancel_callback
        ],
        allow_reentry=True,
        name="sell_conversation"
    )

    application.add_handler(conv_handler)
# handlers/my.py
import json
import logging
import math

# InputMediaPhoto QO'SHILDI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from database import Database
from my_utils import safe_send
from app import CHANNEL_ID

logger = logging.getLogger(__name__)

ADS_PER_PAGE = 1  # Har sahifada nechta e'lon ko'rsatilishi
db = Database()


# =========================
# KEYBOARD
# =========================
def get_ad_keyboard(ad_id: int, page: int, total_pages: int):
    buttons = [
        [
            InlineKeyboardButton("🗑️ O'chirish", callback_data=f"delete_myad_{ad_id}"),
            InlineKeyboardButton("✅ Sotildi", callback_data=f"sold_myad_{ad_id}")
        ]
    ]

    pagination = []
    if page > 1:
        pagination.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page - 1}"))
    if page < total_pages:
        pagination.append(InlineKeyboardButton("➡️ Keyingi", callback_data=f"page_{page + 1}"))

    if pagination:
        buttons.append(pagination)

    return InlineKeyboardMarkup(buttons)


# =========================
# OLD MESSAGES CLEANER
# =========================
async def clear_previous_my_ads_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if "my_ads_messages" in context.chat_data:
        for msg_id in context.chat_data["my_ads_messages"]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass
        context.chat_data["my_ads_messages"] = []


# =========================
# MENING E'LONLARIM
# =========================
async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    chat_id = update.effective_chat.id
    telegram_id = update.effective_user.id

    user_id = await db.get_user_id(telegram_id)
    if not user_id:
        await safe_send(context.bot, chat_id, "⚠️ Siz hali ro‘yxatdan o‘tmagansiz.")
        return

    ads = await db.get_user_ads(user_id)
    if not ads:
        await safe_send(context.bot, chat_id, "📭 Sizda hozircha hech qanday e'lon yo‘q.")
        return

    total_pages = max(1, math.ceil(len(ads) / ADS_PER_PAGE))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * ADS_PER_PAGE
    current_ads = ads[start_idx:start_idx + ADS_PER_PAGE]

    await clear_previous_my_ads_messages(context, chat_id)
    sent_message_ids = []

    for ad in current_ads:
        photos = ad.get('photos', [])
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except:
                photos = []

        ad_text = (
            f"<b>📦 Mahsulot:</b> {ad['product']}\n"
            f"<b>💰 Narxi:</b> {ad['price']} so‘m\n"
            f"<b>⚖️ Miqdor:</b> {ad['amount']}\n"
            f"<b>📍 Manzil:</b> {ad['location']}\n"
            f"<b>📞 Telefon:</b> {ad['phone']}\n"
            f"<b>📝 Izoh:</b> {ad.get('description') or 'Yo‘q'}\n"
            f"<b>🆔 ID:</b> {ad['id']}\n"
            f"<b>📊 Holati:</b> {ad.get('status', 'unknown').upper()}"
        )

        try:
            if photos:
                if len(photos) > 1:
                    # KO'P RASMLI HOLAT (ALBOM)
                    media = [InputMediaPhoto(photos[0], caption=ad_text, parse_mode="HTML")]
                    for p in photos[1:]:
                        media.append(InputMediaPhoto(p))

                    msgs = await context.bot.send_media_group(chat_id=chat_id, media=media)
                    for m in msgs: sent_message_ids.append(m.message_id)

                    # Tugmalarni alohida xabar qilib yuboramiz (chunki albomga biriktirib bo'lmaydi)
                    control_msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text="⚙️ Boshqaruv:",
                        reply_markup=get_ad_keyboard(ad['id'], page, total_pages)
                    )
                    sent_message_ids.append(control_msg.message_id)
                else:
                    # BITTA RASMLI HOLAT
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photos[0],
                        caption=ad_text,
                        parse_mode="HTML",
                        reply_markup=get_ad_keyboard(ad['id'], page, total_pages)
                    )
                    sent_message_ids.append(msg.message_id)
            else:
                # RASMSIZ HOLAT
                msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=ad_text,
                    parse_mode="HTML",
                    reply_markup=get_ad_keyboard(ad['id'], page, total_pages)
                )
                sent_message_ids.append(msg.message_id)

        except Exception as e:
            logger.error(f"Error showing ad {ad['id']}: {e}")

    context.chat_data["my_ads_messages"] = sent_message_ids
    context.user_data['my_ads_current_page'] = page


# user_callback_handler va my_handlers qismlari o'zgarishsiz qoladi
async def user_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Siz yuborgan mavjud kod (o'zgarishsiz)
    query = update.callback_query
    await query.answer()
    # ... qolgan barcha kodlaringiz ...
    # (Bu yerda o'zgarish yo'q, hamma narsa avvalgidek qoladi)
    data = query.data
    telegram_id = query.from_user.id
    user_id = await db.get_user_id(telegram_id)

    if not user_id:
        await query.answer("⚠️ Foydalanuvchi topilmadi!", show_alert=True)
        return

    if data.startswith("delete_myad_"):
        ad_id = int(data.split("_")[-1])
        ad = await db.get_ad_by_id(ad_id)

        if ad and ad.get('user_id') == user_id:
            await db.delete_ad(ad_id, user_id)
            try:
                await query.message.edit_text("🗑️ E'lon o‘chirildi!")
            except:
                try:
                    await query.message.delete()
                except:
                    pass

            channel_message_id = ad.get('channel_post_id')
            if channel_message_id:
                try:
                    await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=channel_message_id)
                except:
                    pass
        else:
            await query.answer("⚠️ Bu e'lon sizniki emas!", show_alert=True)

    elif data.startswith("sold_myad_"):
        ad_id = int(data.split("_")[-1])
        ad = await db.get_ad_by_id(ad_id)
        if ad and ad.get('user_id') == user_id:
            await db.mark_as_sold(ad_id)
            try:
                await query.message.edit_text("✅ Sotildi deb belgilandi!")
            except:
                pass

            channel_message_id = ad.get('channel_post_id')
            if channel_message_id:
                try:
                    await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=channel_message_id)
                except:
                    pass
        else:
            await query.answer("⚠️ Bu e'lon sizniki emas!", show_alert=True)

    elif data.startswith("page_"):
        page = int(data.split("_")[-1])
        await clear_previous_my_ads_messages(context, query.message.chat_id)
        await my_ads(update, context, page)


def my_handlers(application):
    application.add_handler(MessageHandler(filters.Regex("^📄 Mening e'lonlarim$"), my_ads))
    application.add_handler(CallbackQueryHandler(user_callback_handler, pattern="^(delete_myad_|sold_myad_|page_)"))
    return application
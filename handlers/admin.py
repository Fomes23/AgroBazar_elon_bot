# handlers/admin.py
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
from telegram.ext import CallbackQueryHandler, ContextTypes, CommandHandler

from database import Database                   # Global db
from my_utils import safe_send             # Bizning safe_send

logger = logging.getLogger(__name__)

# ================= SOZLAMALAR =================
# app.py dan import qilamiz (to'g'ri nomlar bilan)
from app import CHANNEL_ID, ADMIN_IDS, BOT_USERNAME

db = Database()

# ADMIN_IDS ni ro'yxat sifatida saqlash yaxshiroq
ADMINS = ADMIN_IDS if isinstance(ADMIN_IDS, list) else [ADMIN_IDS]


# ================= KEYBOARDS =================
def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📬 Kutayotgan e'lonlar", callback_data="view_pending_ads")],
        [InlineKeyboardButton("📊 Statistika", callback_data="view_stats")]
    ])


def admin_ad_keyboard(ad_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_approve_{ad_id}"),
        InlineKeyboardButton("❎ Rad etish", callback_data=f"admin_reject_{ad_id}")
    ]])


# ================= ADMIN PANEL =================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        await safe_send(
            context.bot,
            chat_id=update.effective_chat.id,
            text="⚠️ Siz admin emassiz!"
        )
        return

    await safe_send(
        context.bot,
        chat_id=update.effective_chat.id,
        text="🛠 *Admin paneliga xush kelibsiz*",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )


# ================= PENDING E'LONLARNI YUBORISH =================
async def send_pending_ads_to_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    ads = await db.get_pending_ads()

    if not ads:
        await safe_send(context.bot, chat_id, "📭 Hozircha kutayotgan e'lonlar yo‘q.")
        return

    for ad in ads:
        full_ad = await db.get_ad_with_user(ad['id'])
        if not full_ad:
            continue

        text = (
            f"🆔 ID: {full_ad['id']}\n"
            f"📦 Mahsulot: {full_ad['product']}\n"
            f"💰 Narx: {full_ad['price']} so‘m\n"
            f"⚖️ Miqdor: {full_ad['amount']}\n"
            f"📍 Manzil: {full_ad['location']}\n"
            f"📞 Telefon: {full_ad['phone']}\n"
            f"📝 Izoh: {full_ad.get('description') or 'Yo‘q'}\n"
            f"👤 Foydalanuvchi ID: {full_ad.get('telegram_id')}"
        )

        photos = full_ad.get("photos", [])

        try:
            if photos:
                media = [
                    InputMediaPhoto(media=photo, caption=text if i == 0 else None)
                    for i, photo in enumerate(photos)
                ]
                await context.bot.send_media_group(chat_id=chat_id, media=media)
                await safe_send(
                    context.bot,
                    chat_id=chat_id,
                    text="👇 Quyidagi tugmalardan birini tanlang:",
                    reply_markup=admin_ad_keyboard(full_ad['id'])
                )
            else:
                await safe_send(
                    context.bot,
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=admin_ad_keyboard(full_ad['id'])
                )
        except Exception as e:
            logger.error(f"Admin ga e'lon yuborishda xato (ID: {full_ad['id']}): {e}")


# ================= CALLBACK HANDLER =================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("admin_approve_"):
        ad_id = int(data.split("_")[-1])
        await approve_ad(query, context, ad_id)

    elif data.startswith("admin_reject_"):
        ad_id = int(data.split("_")[-1])
        await reject_ad(query, context, ad_id)

    elif data == "view_pending_ads":
        await send_pending_ads_to_admin(context, query.message.chat_id)

    elif data == "view_stats":
        await show_stats(query, context)


# ================= E'LONNI TASDIQLASH =================
async def approve_ad(query, context: ContextTypes.DEFAULT_TYPE, ad_id: int):
    ad = await db.get_ad_with_user(ad_id)
    username = await db.get_username(ad_id)
    if not ad:
        await query.answer("E'lon topilmadi!", show_alert=True)
        return

    text = (
        f"📦 Mahsulot: {ad['product']}\n"
        f"💰 Narx: {ad['price']} so‘m\n"
        f"⚖️ Miqdor: {ad['amount']}\n"
        f"📍 Manzil: {ad['location']}\n"
        f"📞 Telefon: {ad['phone']}\n"
        f"👤 Telegram: @{username}\n"
        f"📝 Izoh: {ad.get('description') or 'Yo‘q'}\n\n"
        f"📢 Kanalda e’lon berish quyidagi bot orqali amalga oshiriladi 👉 {BOT_USERNAME}"
    )

    photos = ad.get("photos", [])
    channel_post_id = None

    try:
        if photos:
            media = [InputMediaPhoto(media=photo, caption=text if i == 0 else None)
                     for i, photo in enumerate(photos)]
            sent_messages = await context.bot.send_media_group(
                chat_id=CHANNEL_ID, media=media
            )
            if sent_messages:
                channel_post_id = sent_messages[0].message_id
        else:
            sent = await context.bot.send_message(
                chat_id=CHANNEL_ID, text=text, parse_mode="Markdown"
            )
            channel_post_id = sent.message_id

        # Database ni yangilash
        await db.update_ad_status(ad_id, "approved", channel_post_id)

        # Admin interfeysini yangilash
        await query.message.edit_text("✅ *Tasdiqlandi va kanalga joylashtirildi!*", parse_mode="Markdown")

        # Foydalanuvchiga xabar yuborish
        if ad.get("telegram_id"):
            await safe_send(
                context.bot,
                chat_id=ad["telegram_id"],
                text="🎉 *Tabriklaymiz!* E'loningiz admin tomonidan tasdiqlandi va kanalga chiqarildi."
            )

    except Exception as e:
        logger.error(f"Approve qilishda xato (ad_id={ad_id}): {e}")
        await query.answer("Xatolik yuz berdi!", show_alert=True)


# ================= E'LONNI RAD ETISH =================
async def reject_ad(query, context: ContextTypes.DEFAULT_TYPE, ad_id: int):
    try:
        await db.update_ad_status(ad_id, "rejected")
        await query.message.edit_text("❌ *Sizning e`loningiz rad etildi*", parse_mode="Markdown")
        await query.answer("Rad etildi")
    except Exception as e:
        logger.error(f"Reject qilishda xato: {e}")
        await query.answer("Xatolik yuz berdi", show_alert=True)


# ================= STATISTIKA =================
async def show_stats(query, context: ContextTypes.DEFAULT_TYPE):
    approved = len(await db.get_approved_ads())
    pending = len(await db.get_pending_ads())
    # rejected = len(await db.get_ads_by_status("rejected"))  # agar kerak bo'lsa

    text = f"""📊 *Statistika*

✅ Tasdiqlangan e'lonlar: {approved} ta
📬 Kutayotgan e'lonlar: {pending} ta"""

    await safe_send(
        context.bot,
        chat_id=query.message.chat_id,
        text=text,
        parse_mode="Markdown"
    )


# ================= HANDLERLARNI RO‘YXATGA OLISH =================
def admin_handlers(application):
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_callback))
    return application
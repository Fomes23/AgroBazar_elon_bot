import logging
import asyncio
from telegram.ext import ApplicationBuilder

# Handlerlar va boshqa importlar (o'zgarishsiz qoladi)
from handlers.start import start_handlers
from handlers.elon import elon_handlers
from handlers.my import my_handlers
from handlers.admin import admin_handlers
from handlers.yordam import yordam_handlers
from handlers.kanal import kanal_handlers

from database import Database
from app import TOKEN, CHANNEL_ID

# Global db obyekti
db = Database()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def auto_cleaner(application):
    """DELETED va SOLD e'lonlarni kanaldan to'liq (rasmlari bilan) o'chirish"""
    while True:
        try:
            await db._ensure_connection()
            async with db.conn.execute(
                    "SELECT * FROM ads WHERE status IN ('DELETED', 'SOLD') AND channel_post_id IS NOT NULL"
            ) as cursor:
                rows = await cursor.fetchall()
                ads_to_clean = db._process_ads(rows)

            for ad in ads_to_clean:
                post_id = ad.get("channel_post_id")
                ad_id = ad.get("id")

                try:
                    # 1. Asosiy xabarni o'chirish
                    await application.bot.delete_message(chat_id=CHANNEL_ID, message_id=post_id)

                    # 2. AGAR RASMLAR KO'P BO'LSA:
                    # Telegramda albom yuborilganda ID-lar ketma-ket bo'ladi (masalan: 100, 101, 102)
                    # Keyingi 2 ta ID-ni ham o'chirishga harakat qilamiz (chunki max 3 ta rasm deganmiz)
                    for extra_id in [post_id + 1, post_id + 2]:
                        try:
                            await application.bot.delete_message(chat_id=CHANNEL_ID, message_id=extra_id)
                        except:
                            continue  # Agar rasm bitta bo'lsa, xato bermasligi uchun

                    logger.info(f"🗑️ Kanal e'loni to'liq tozalandi: {post_id}")
                except Exception as e:
                    logger.warning(f"O'chirishda xatolik: {e}")

                # Bazada post ID ni tozalaymiz
                await db.clear_channel_post(ad_id)

        except Exception as e:
            logger.error(f"Cleaner xatosi: {e}")

        await asyncio.sleep(60)


async def post_init(application):
    # DB ulanishini shu yerda ochamiz (chunki bu async)
    await db.connect()
    logger.info("✅ Database bilan ulanish ochildi.")

    await application.bot.set_my_commands([
        ("start", "Botni ishga tushirish"),
        ("admin", "Admin panel"),
    ])
    # Cleaner vazifasini ishga tushirish
    asyncio.create_task(auto_cleaner(application))
    logger.info("🚀 Bot to'liq tayyor!")


async def post_shutdown(application):
    logger.info("🛑 Bot to'xtatilmoqda...")
    await db.close()
    logger.info("✅ Database yopildi.")


def main():
    """Asosiy funksiya endi async emas!"""
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    # Handlerlar
    start_handlers(application)
    elon_handlers(application)
    my_handlers(application)
    admin_handlers(application)
    yordam_handlers(application)
    kanal_handlers(application)

    # BU METOD hamma narsani (loopni ham) o'zi boshqaradi
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Bot to'xtatildi.")
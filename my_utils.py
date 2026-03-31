import asyncio
import logging
from telegram.error import TimedOut, NetworkError, RetryAfter, TelegramError

# Logger sozlash ( tavsiya etiladi )
logger = logging.getLogger(__name__)


async def safe_send(
    bot,
    chat_id: int,
    text: str,
    parse_mode: str = None,
    reply_markup=None,
    max_retries: int = 3,
    delay: int = 2,
    **kwargs  # Qo'shimcha parametrlar uchun (masalan: disable_notification, protect_content va h.k.)
):
    """
    Xatoliklarni ushlab, avtomatik qayta urinish bilan xabar yuboruvchi xavfsiz funksiya.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                **kwargs
            )

        except RetryAfter as e:
            # Telegram "Too Many Requests" berganda (flood control)
            wait_time = e.retry_after + 1
            logger.warning(
                f"Flood control: {wait_time} soniya kutish kerak. Chat ID: {chat_id}"
            )
            await asyncio.sleep(wait_time)
            continue

        except (TimedOut, NetworkError) as e:
            if attempt == max_retries:
                logger.error(
                    f"Xabar yuborilmadi ({max_retries} urinishdan keyin). "
                    f"Chat ID: {chat_id} | Xato: {e}"
                )
                break

            logger.warning(
                f"{attempt}-urinish muvaffaqiyatsiz. Chat ID: {chat_id} | Xato: {e}. "
                f"{delay} soniyadan keyin qayta uriniladi..."
            )
            await asyncio.sleep(delay * attempt)  # exponential backoff

        except TelegramError as e:
            # Boshqa Telegram xatolari (masalan: chat not found, blocked va h.k.)
            if "chat not found" in str(e).lower() or "bot was blocked" in str(e).lower():
                logger.warning(f"Chatga yuborib bo'lmadi (foydalanuvchi botni bloklagan yoki o'chirgan). Chat ID: {chat_id}")
            else:
                logger.error(f"TelegramError: {e} | Chat ID: {chat_id}")
            break  # Bu turdagi xatolarda qayta urinmaslik yaxshiroq

        except Exception as e:
            # Kutilmagan xatolar
            logger.exception(f"Kutilmagan xato safe_send da: {e} | Chat ID: {chat_id}")
            break

    return None  # Agar hammasi muvaffaqiyatsiz bo'lsa
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "bot_config.json"
DATA_PATH = BASE_DIR / "user_state.json"
ANALYTICS_PATH = BASE_DIR / "analytics.json"

ASKING_IMAGES = 1
ASKING_SLOT = 2

DEFAULT_CONFIG: Dict[str, Any] = {
    "bot_token": "PASTE_YOUR_BOT_TOKEN",
    "admin_chat_id": 323258296,
    "brand_name": "Александр Зарецкий",
    "brand_role": "психолог и проводник во внутреннюю опору",
    "timezone_note": "Europe/Minsk",
    "booking_mode": "manual_slots",
    "booking_link": "https://t.me/Alex_Zaretsky",
    "free_video_file_id": "BAACAgIAAxkBAAFG4sFp2M_t02YDOBNUS66t5vaL8W87ywACnJYAAswxyUqUDYEVMwABL747BA",
    "meditation_file_id": "BAACAgIAAxkBAAFG4plp2M8cUgkDLnHlby4S4K4OUJLtaQACTJUAAswxyUoWDub5fumvkTsE",
    "welcome_text": "Привет, {name}. Я рад, что ты здесь. Ниже — первое видео, которое поможет тебе мягко войти в процесс.",
    "free_video_caption": "Стартовое видео. Посмотри его в спокойной обстановке.",
    "meditation_intro_text": "Теперь переходи к короткой медитации. Она поможет услышать себя глубже.",
    "meditation_caption": "Медитация. Лучше слушать в тишине и без спешки.",
    "images_prompt_text": "После практики напиши одним сообщением ответы на вопросы:\n1) Что ты сейчас чувствуешь?\n2) Что особенно откликнулось?\n3) Какие образы, мысли или воспоминания пришли?\n4) Что бы ты хотел изменить в своей жизни уже сейчас?\n\nМожно также приложить фото или скрин, но главное — текст одним сообщением.",
    "images_thanks_text": "Спасибо. Я получил твой ответ. Ниже можешь выбрать удобный слот для созвона.",
    "booking_intro_text": "Выбери удобный слот и отправь его одним сообщением точно в таком же виде, как в списке ниже.",
    "booking_success_text": "Спасибо. Я передал твою заявку. Скоро свяжусь с тобой для подтверждения времени.",
    "meditation_reminder_text": "Напоминание: если ещё не дошёл до практики, сейчас хорошее время посмотреть медитацию.",
    "images_reminder_text": "Напоминание: если уже посмотрел материалы, пришли мне одним сообщением свои ответы и ощущения.",
    "call_reminder_text": "Напоминание: если готов двигаться дальше, выбери удобный слот для созвона.",
    "fallback_no_video_text": "Видео сейчас не настроено. Проверь free_video_file_id или meditation_file_id в bot_config.json.",
    "fallback_no_slots_text": "Слоты пока не настроены. Временно напиши мне напрямую в Telegram: {booking_link}",
    "slots": {
        "Mon": ["11:00", "14:00", "18:00"],
        "Tue": ["12:00", "16:00"],
        "Wed": ["11:00", "15:00", "19:00"],
        "Thu": ["12:00", "17:00"],
        "Fri": ["11:00", "14:00"],
        "Sat": [],
        "Sun": [],
    },
}


def ensure_files() -> None:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    if not DATA_PATH.exists():
        DATA_PATH.write_text("{}", encoding="utf-8")
    if not ANALYTICS_PATH.exists():
        ANALYTICS_PATH.write_text(json.dumps({"events": [], "summary": {}}, ensure_ascii=False, indent=2), encoding="utf-8")



def merge_dicts(base: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in custom.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result



def load_config() -> Dict[str, Any]:
    ensure_files()
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = merge_dicts(DEFAULT_CONFIG, raw)
    return config



def load_data() -> Dict[str, Any]:
    ensure_files()
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))



def save_data(data: Dict[str, Any]) -> None:
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def load_analytics() -> Dict[str, Any]:
    ensure_files()
    return json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))



def save_analytics(data: Dict[str, Any]) -> None:
    ANALYTICS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def track_event(user_id: int, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
    analytics = load_analytics()
    event = {
        "user_id": user_id,
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data or {},
    }
    analytics.setdefault("events", []).append(event)
    summary = analytics.setdefault("summary", {})
    summary[event_type] = summary.get(event_type, 0) + 1
    save_analytics(analytics)



def set_stage(user_id: int, **kwargs: Any) -> None:
    data = load_data()
    state = data.get(str(user_id), {})
    state.update(kwargs)
    state["updated_at"] = datetime.utcnow().isoformat()
    data[str(user_id)] = state
    save_data(data)



def render_text(template: str, **kwargs: Any) -> str:
    safe = {k: ("" if v is None else str(v)) for k, v in kwargs.items()}
    try:
        return template.format(**safe)
    except Exception:
        return template



def user_display_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "друг"
    return user.first_name or user.full_name or "друг"



def slot_lines(config: Dict[str, Any]) -> List[str]:
    day_names = {
        "Mon": "Пн",
        "Tue": "Вт",
        "Wed": "Ср",
        "Thu": "Чт",
        "Fri": "Пт",
        "Sat": "Сб",
        "Sun": "Вс",
    }
    slots = config.get("slots", {}) or {}
    lines: List[str] = []
    for key in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        values = slots.get(key, []) or []
        if values:
            lines.append(f"{day_names[key]}: {', '.join(values)}")
    return lines



def slots_text(config: Dict[str, Any]) -> str:
    lines = slot_lines(config)
    if not lines:
        return render_text(
            config.get("fallback_no_slots_text", DEFAULT_CONFIG["fallback_no_slots_text"]),
            booking_link=config.get("booking_link", ""),
        )
    return "\n".join(lines)


async def send_telegram_video(target_message, file_id: str, caption: str, fallback_text: str) -> bool:
    if file_id and not file_id.startswith("PASTE_"):
        await target_message.reply_video(video=file_id, caption=caption)
        return True
    await target_message.reply_text(fallback_text)
    return False


async def schedule_followups(application: Application, chat_id: int) -> None:
    job_queue = application.job_queue
    if job_queue is None:
        return
    names = [
        f"meditationreminder_{chat_id}",
        f"imagesreminder_{chat_id}",
        f"callreminder_{chat_id}",
    ]
    for name in names:
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    job_queue.run_once(remind_meditation, when=timedelta(hours=24), chat_id=chat_id, name=names[0])
    job_queue.run_once(remind_images, when=timedelta(hours=48), chat_id=chat_id, name=names[1])
    job_queue.run_once(remind_call, when=timedelta(hours=72), chat_id=chat_id, name=names[2])


async def remind_meditation(context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    chat_id = context.job.chat_id
    track_event(chat_id, "reminder_meditation_sent")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Получить медитацию", callback_data="get_meditation")]])
    await context.bot.send_message(chat_id=chat_id, text=config.get("meditation_reminder_text", DEFAULT_CONFIG["meditation_reminder_text"]), reply_markup=keyboard)


async def remind_images(context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    chat_id = context.job.chat_id
    track_event(chat_id, "reminder_images_sent")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Отправить ответы", callback_data="share_images")]])
    await context.bot.send_message(chat_id=chat_id, text=config.get("images_reminder_text", DEFAULT_CONFIG["images_reminder_text"]), reply_markup=keyboard)


async def remind_call(context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    chat_id = context.job.chat_id
    track_event(chat_id, "reminder_call_sent")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выбрать слот", callback_data="book_call")]])
    await context.bot.send_message(chat_id=chat_id, text=config.get("call_reminder_text", DEFAULT_CONFIG["call_reminder_text"]), reply_markup=keyboard)


async def send_meditation_flow(message, user_id: int, config: Dict[str, Any]) -> None:
    set_stage(user_id, stage="meditation_sent")
    track_event(user_id, "meditation_requested")
    await message.reply_text(config.get("meditation_intro_text", DEFAULT_CONFIG["meditation_intro_text"]))
    await send_telegram_video(
        message,
        file_id=(config.get("meditation_file_id") or "").strip(),
        caption=config.get("meditation_caption", DEFAULT_CONFIG["meditation_caption"]),
        fallback_text=config.get("fallback_no_video_text", DEFAULT_CONFIG["fallback_no_video_text"]),
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Отправить ответы", callback_data="share_images")]])
    await message.reply_text("После практики нажми кнопку ниже и пришли ответы одним сообщением.", reply_markup=keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    name = user_display_name(update)
    user = update.effective_user
    if not update.message or not user:
        return
    set_stage(user.id, stage="start")
    track_event(user.id, "bot_started", {"username": user.username or ""})
    await schedule_followups(context.application, update.effective_chat.id)

    welcome_text = render_text(
        config.get("welcome_text", DEFAULT_CONFIG["welcome_text"]),
        name=name,
        brand_name=config.get("brand_name", ""),
        brand_role=config.get("brand_role", ""),
    )
    await update.message.reply_text(welcome_text)
    await send_telegram_video(
        update.message,
        file_id=(config.get("free_video_file_id") or "").strip(),
        caption=config.get("free_video_caption", DEFAULT_CONFIG["free_video_caption"]),
        fallback_text=config.get("fallback_no_video_text", DEFAULT_CONFIG["fallback_no_video_text"]),
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Получить медитацию", callback_data="get_meditation")]])
    await update.message.reply_text("Когда будешь готов, нажми кнопку ниже.", reply_markup=keyboard)


async def get_meditation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    config = load_config()
    if not query:
        return
    await query.answer()
    await send_meditation_flow(query.message, query.from_user.id, config)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def share_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config = load_config()
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    set_stage(query.from_user.id, stage="awaiting_images")
    track_event(query.from_user.id, "images_prompt_opened")
    await query.message.reply_text(config.get("images_prompt_text", DEFAULT_CONFIG["images_prompt_text"]))
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    return ASKING_IMAGES


async def receive_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config = load_config()
    user = update.effective_user
    message = update.message
    if not user or not message:
        return ConversationHandler.END

    text = (message.text or message.caption or "").strip()
    photos = message.photo or []
    document = message.document

    set_stage(user.id, stage="images_received", images_text=text)
    track_event(user.id, "images_received", {"text_length": len(text), "photos_count": len(photos)})

    admin_chat_id = int(config.get("admin_chat_id", 0) or 0)
    if admin_chat_id:
        username = f"@{user.username}" if user.username else "—"
        admin_text = (
            "Новая заявка от пользователя\n\n"
            f"Имя: {user.full_name}\n"
            f"Username: {username}\n"
            f"Chat ID: {user.id}\n\n"
            "Ответ пользователя:\n"
            f"{text or 'Пользователь отправил фото/файл без текста.'}"
        )
        await context.bot.send_message(chat_id=admin_chat_id, text=admin_text)
        if photos:
            await context.bot.send_photo(chat_id=admin_chat_id, photo=photos[-1].file_id, caption=f"Фото от {user.full_name}")
        if document:
            await context.bot.send_document(chat_id=admin_chat_id, document=document.file_id, caption=f"Файл от {user.full_name}")

    thanks_text = config.get("images_thanks_text", DEFAULT_CONFIG["images_thanks_text"])
    booking_text = config.get("booking_intro_text", DEFAULT_CONFIG["booking_intro_text"])
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выбрать слот", callback_data="book_call")]])
    await message.reply_text(f"{thanks_text}\n\n{booking_text}\n\n{slots_text(config)}", reply_markup=keyboard)
    return ConversationHandler.END


async def book_call(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config = load_config()
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    set_stage(query.from_user.id, stage="booking_started")
    track_event(query.from_user.id, "book_call_clicked")
    await query.message.reply_text(f"{config.get('booking_intro_text', DEFAULT_CONFIG['booking_intro_text'])}\n\n{slots_text(config)}")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    return ASKING_SLOT


async def receive_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config = load_config()
    user = update.effective_user
    message = update.message
    if not user or not message:
        return ConversationHandler.END

    chosen_slot = (message.text or "").strip()
    set_stage(user.id, stage="slot_requested", chosen_slot=chosen_slot)
    track_event(user.id, "slot_requested", {"slot": chosen_slot})

    admin_chat_id = int(config.get("admin_chat_id", 0) or 0)
    if admin_chat_id:
        username = f"@{user.username}" if user.username else "—"
        admin_text = (
            "Запрос на созвон\n\n"
            f"Имя: {user.full_name}\n"
            f"Username: {username}\n"
            f"Chat ID: {user.id}\n"
            f"Выбранный слот: {chosen_slot}"
        )
        await context.bot.send_message(chat_id=admin_chat_id, text=admin_text)

    await message.reply_text(config.get("booking_success_text", DEFAULT_CONFIG["booking_success_text"]))
    return ConversationHandler.END


async def meditation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not update.message or not update.effective_user:
        return
    await send_meditation_flow(update.message, update.effective_user.id, config)


async def call_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not update.message or not update.effective_user:
        return
    set_stage(update.effective_user.id, stage="booking_prompted")
    track_event(update.effective_user.id, "call_command_used")
    await update.message.reply_text(f"{config.get('booking_intro_text', DEFAULT_CONFIG['booking_intro_text'])}\n\n{slots_text(config)}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Ок, остановил текущий шаг. Можешь снова использовать /start.")
    elif update.callback_query:
        await update.callback_query.answer()
    return ConversationHandler.END



def main() -> None:
    config = load_config()
    token = (config.get("bot_token") or "").strip()
    if not token or token.startswith("PASTE_"):
        raise ValueError("Укажи реальный bot_token в bot_config.json")

    application = Application.builder().token(token).build()

    conv_images = ConversationHandler(
        entry_points=[CallbackQueryHandler(share_images, pattern="^share_images$")],
        states={
            ASKING_IMAGES: [MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, receive_images)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    conv_booking = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_call, pattern="^book_call$")],
        states={
            ASKING_SLOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_slot)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("meditation", meditation_command))
    application.add_handler(CommandHandler("call", call_command))
    application.add_handler(CallbackQueryHandler(get_meditation, pattern="^get_meditation$"))
    application.add_handler(conv_images)
    application.add_handler(conv_booking)

    logger.info("Bot started")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

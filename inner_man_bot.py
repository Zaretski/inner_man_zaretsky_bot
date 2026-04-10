import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, ContextTypes, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path('output/bot_config.json')
DATA_PATH = Path('output/user_state.json')
ANALYTICS_PATH = Path('output/analytics.json')

ASKING_IMAGES = 1
ASKING_SLOT = 2

DEFAULT_CONFIG = {"bot_token": "8768034861:AAFSZWwz3zUxptHS0bRvKgcTZI9TJ-0KSQw", "admin_chat_id": "323258296", "free_video_file_id": "AAMCAgADGQEC_8JWadi3hunBsEEPHlQz3bn-YDAaV2sAAkyVAALMMclKp5Wldvk-YBsBAAdtAAM7BA", "meditation_file_id": "AAMCAgADGQEC_8Ozadi5w6JLMwtIRUMAATAgmk6wcxPHAAJZlQACzDHJSj7ix54VNsbfAQAHbQADOwQ", "booking_mode": "manual_slots", "booking_link": "https://t.me/Alex_Zaretsky", "timezone_note": "Europe/Minsk", "slots": {"Mon": ["11:00", "14:00", "18:00"], "Tue": ["12:00", "16:00"], "Wed": ["11:00", "15:00", "19:00"], "Thu": ["12:00", "17:00"], "Fri": ["11:00", "14:00"], "Sat": [], "Sun": []}, "price_note": "Если захочешь пойти глубже, у меня есть индивидуальная работа по теме внутреннего мужчины.", "brand_name": "Александр Зарецкий", "brand_role": "психолог, специалист по глубинной психологии отношений"}

def ensure_files():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding='utf-8')
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding='utf-8')
    if not ANALYTICS_PATH.exists():
        ANALYTICS_PATH.write_text(json.dumps({"events": [], "summary": {}}, ensure_ascii=False, indent=2), encoding='utf-8')

def load_config():
    ensure_files()
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))

def load_data():
    ensure_files()
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))

def save_data(data):
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def load_analytics():
    ensure_files()
    return json.loads(ANALYTICS_PATH.read_text(encoding='utf-8'))

def save_analytics(analytics):
    ANALYTICS_PATH.write_text(json.dumps(analytics, ensure_ascii=False, indent=2), encoding='utf-8')

def track_event(user_id: int, event_type: str, data: dict = None):
    analytics = load_analytics()
    event = {"user_id": user_id, "event": event_type, "timestamp": datetime.utcnow().isoformat(), "data": data or {}}
    analytics["events"].append(event)
    summary = analytics.get("summary", {})
    summary[event_type] = summary.get(event_type, 0) + 1
    analytics["summary"] = summary
    save_analytics(analytics)
    logger.info(f"Analytics: {event_type} by user {user_id}")

def set_stage(user_id: int, **kwargs):
    data = load_data()
    state = data.get(str(user_id), {})
    state.update(kwargs)
    state['updated_at'] = datetime.utcnow().isoformat()
    data[str(user_id)] = state
    save_data(data)

def next_slots_text(config):
    slots = config.get('slots', {})
    names = {'Mon': 'Понедельник', 'Tue': 'Вторник', 'Wed': 'Среда', 'Thu': 'Четверг', 'Fri': 'Пятница', 'Sat': 'Суббота', 'Sun': 'Воскресенье'}
    lines = []
    for key in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
        values = slots.get(key, [])
        if values:
            lines.append(f"• {names[key]}: {', '.join(values)}")
    return '\n'.join(lines) if lines else 'Пока слоты не заполнены.'

async def schedule_followups(application, chat_id: int):
    job_queue = application.job_queue
    for name in [f"meditation_reminder_{chat_id}", f"images_reminder_{chat_id}", f"call_reminder_{chat_id}"]:
        current = job_queue.get_jobs_by_name(name)
        for job in current:
            job.schedule_removal()
    job_queue.run_once(remind_meditation, when=timedelta(hours=24), chat_id=chat_id, name=f"meditation_reminder_{chat_id}")
    job_queue.run_once(remind_images, when=timedelta(hours=48), chat_id=chat_id, name=f"images_reminder_{chat_id}")
    job_queue.run_once(remind_call, when=timedelta(hours=72), chat_id=chat_id, name=f"call_reminder_{chat_id}")

async def remind_meditation(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    track_event(chat_id, "reminder_meditation_sent")
    await context.bot.send_message(chat_id=chat_id, text="Напоминаю о медитации 🌿\n\nЕсли ты посмотрела бесплатное видео, следующим шагом будет медитация на встречу с внутренним мужчиной. Именно она обычно даёт первый сильный инсайт.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎧 Получить медитацию", callback_data="get_meditation")]]))

async def remind_images(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    track_event(chat_id, "reminder_images_sent")
    await context.bot.send_message(chat_id=chat_id, text="Если ты уже сделала медитацию, пришли мне короткое описание образов.\n\nМожно очень просто: кто был мужчина, как выглядел, как себя вёл и что ты почувствовала. Даже 3–4 короткие фразы уже достаточно.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Описать образы", callback_data="share_images")]]))

async def remind_call(context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    chat_id = context.job.chat_id
    track_event(chat_id, "reminder_call_sent")
    buttons = [[InlineKeyboardButton("📅 Записаться", url=config.get('booking_link', 'https://t.me'))]] if config.get('booking_mode') == 'booking_link' else [[InlineKeyboardButton("📞 Выбрать время", callback_data="book_call")]]
    await context.bot.send_message(chat_id=chat_id, text="Если хочешь, я могу помочь тебе расшифровать образы на коротком созвоне.\n\nНа встрече мы разберём, что именно показала медитация, и я скажу, куда двигаться дальше без давления и навязывания.", reply_markup=InlineKeyboardMarkup(buttons))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    user = update.effective_user
    set_stage(user.id, stage='start')
    await schedule_followups(context.application, update.effective_chat.id)
    track_event(user.id, "bot_started", {"username": user.username, "first_name": user.first_name, "last_name": user.last_name})
    text = f"Привет, {user.first_name or 'дорогая'} 👋\n\nЯ — {config['brand_name']}, {config['brand_role']}.\n\nЕсли в отношениях у тебя снова и снова повторяется один и тот же болезненный сценарий, это не случайность.\n\nОбраз внутреннего мужчины часто влияет на то, каких мужчин ты выбираешь, чего ждёшь от отношений и как переживаешь близость.\n\nНиже — бесплатное видео, где я простым языком объясняю, кто такой внутренний мужчина и почему эта тема так сильно влияет на личную жизнь."
    await update.message.reply_text(text)
    try:
        await update.message.reply_video(video=config['free_video_file_id'], caption="▶️ Смотри бесплатное видео прямо здесь")
        track_event(user.id, "free_video_sent")
    except Exception as e:
        logger.error(f"Ошибка отправки видео: {e}")
        track_event(user.id, "free_video_send_error", {"error": str(e)})
    await update.message.reply_text("После просмотра — нажми кнопку ниже, чтобы получить медитацию →", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🧘 Получить медитацию", callback_data='get_meditation')]]))

async def get_meditation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    query = update.callback_query
    await query.answer()
    set_stage(query.from_user.id, stage='meditation_sent')
    track_event(query.from_user.id, "meditation_requested")
    text = "Хорошо, идём глубже 🌿\n\nЭто медитация-встреча с образом внутреннего мужчины. Делай её в спокойной обстановке, лучше в наушниках.\n\nНе старайся анализировать во время процесса. Просто наблюдай, что приходит: образ, поведение, дистанция, эмоции, ощущения в теле.\n\nПосле медитации нажми кнопку ниже и опиши, что увидела. Можно коротко, без длинного рассказа."
    await query.message.reply_text(text)
    try:
        await query.message.reply_video(video=config['meditation_file_id'], caption="🎧 Слушай медитацию прямо здесь")
        track_event(query.from_user.id, "meditation_sent")
    except Exception as e:
        logger.error(f"Ошибка отправки медитации: {e}")
        track_event(query.from_user.id, "meditation_send_error", {"error": str(e)})
    await query.message.reply_text("После медитации опиши образы →", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Описать образы", callback_data='share_images')]]))
    await query.edit_message_reply_markup(reply_markup=None)

async def share_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_stage(query.from_user.id, stage='awaiting_images')
    track_event(query.from_user.id, "share_images_clicked")
    text = "Напиши мне ответ одним сообщением. Можно коротко.\n\n1. Кто был этот мужчина\n2. Как он выглядел или во что был одет\n3. Как он себя вёл\n4. Что ты почувствовала рядом с ним\n\nЕсли удобнее, можешь ответить буквально в 3–5 фразах."
    await query.edit_message_text(text)
    return ASKING_IMAGES

async def receive_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    user = update.effective_user
    text = update.message.text
    set_stage(user.id, stage='images_received', images=text)
    track_event(user.id, "images_received", {"text_length": len(text)})
    admin_text = f"🔔 Новое описание образов\n\nИмя: {user.full_name}\nUsername: @{user.username if user.username else 'нет'}\nchat_id: {user.id}\n\nОписание:\n{text}"
    await context.bot.send_message(chat_id=config['admin_chat_id'], text=admin_text)
    await update.message.reply_text(f"Спасибо, я получил твоё описание.\n\nСледующий шаг — короткий разбор, где я помогу тебе увидеть смысл этих образов и связать их с твоим сценарием в отношениях.\n\nЭто не просто знакомство. Это встреча, на которой мы разберём твою медитацию, а если тебе откликнется, я расскажу о формате более глубокой индивидуальной работы.\n\n{config['price_note']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 Выбрать время для разбора", callback_data='book_call')]]))
    return ConversationHandler.END

async def book_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    

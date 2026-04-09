import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path('output/bot_config.json')
DATA_PATH = Path('output/user_state.json')

ASKING_IMAGES = 1
ASKING_SLOT = 2

DEFAULT_CONFIG = {
    "bot_token": "8768034861:AAFSZWwz3zUxptHS0bRvKgcTZI9TJ-0KSQw",
    "admin_chat_id": "323258296",
    "free_video_file_id": "AAMCAgADGQEC_1O-adfx67Qaz67g9ew_vfC9A_haAkUAApafAAK3gcBKa_S3XocyfkYBAAdtAAM7BA",
    "meditation_file_id": "AAMCAgADGQEC_1O4adfx2YUhgNPF3zPIUnC5pO0ILmcAApSfAAK3gcBKGAHuv0Hu0DwBAAdtAAM7BA",
    "booking_mode": "manual_slots",
    "booking_link": "https://t.me/Alex_Zaretsky",
    "timezone_note": "Europe/Minsk",
    "slots": {
        "Mon": ["11:00", "14:00", "18:00"],
        "Tue": ["12:00", "16:00"],
        "Wed": ["11:00", "15:00", "19:00"],
        "Thu": ["12:00", "17:00"],
        "Fri": ["11:00", "14:00"],
        "Sat": [],
        "Sun": []
    },
    "price_note": "Если захочешь пойти глубже, у меня есть индивидуальная работа по теме внутреннего мужчины.",
    "brand_name": "Александр Зарецкий",
    "brand_role": "психолог, специалист по глубинной психологии отношений"
}


def ensure_files():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding='utf-8')
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding='utf-8')


def load_config():
    ensure_files()
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def load_data():
    ensure_files()
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))


def save_data(data):
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def set_stage(user_id: int, **kwargs):
    data = load_data()
    state = data.get(str(user_id), {})
    state.update(kwargs)
    state['updated_at'] = datetime.utcnow().isoformat()
    data[str(user_id)] = state
    save_data(data)


def get_stage(user_id: int):
    data = load_data()
    return data.get(str(user_id), {})


def weekday_map():
    return {
        0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'
    }


def next_slots_text(config):
    slots = config.get('slots', {})
    names = {
        'Mon': 'Понедельник', 'Tue': 'Вторник', 'Wed': 'Среда',
        'Thu': 'Четверг', 'Fri': 'Пятница', 'Sat': 'Суббота', 'Sun': 'Воскресенье'
    }
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
    config = load_config()
    chat_id = context.job.chat_id
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "Напоминаю о медитации 🌿\n\n"
            "Если ты посмотрела бесплатное видео, следующим шагом будет медитация на встречу с внутренним мужчиной. "
            "Именно она обычно даёт первый сильный инсайт."
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎧 Получить медитацию", callback_data="get_meditation")]
        ])
    )


async def remind_images(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "Если ты уже сделала медитацию, пришли мне короткое описание образов.\n\n"
            "Можно очень просто: кто был мужчина, как выглядел, как себя вёл и что ты почувствовала. "
            "Даже 3–4 короткие фразы уже достаточно."
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Описать образы", callback_data="share_images")]
        ])
    )


async def remind_call(context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    chat_id = context.job.chat_id
    mode = config.get('booking_mode', 'manual_slots')
    buttons = []
    if mode == 'booking_link':
        buttons.append([InlineKeyboardButton("📅 Записаться", url=config.get('booking_link', 'https://t.me'))])
    else:
        buttons.append([InlineKeyboardButton("📞 Выбрать время", callback_data="book_call")])
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "Если хочешь, я могу помочь тебе расшифровать образы на коротком созвоне.\n\n"
            "На встрече мы разберём, что именно показала медитация, и я скажу, куда двигаться дальше без давления и навязывания."
        ),
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    user = update.effective_user
    set_stage(user.id, stage='start')
    await schedule_followups(context.application, update.effective_chat.id)

    text = (
        f"Привет, {user.first_name or 'дорогая'} 👋\n\n"
        f"Я — {config['brand_name']}, {config['brand_role']}.\n\n"
        "Если в отношениях у тебя снова и снова повторяется один и тот же болезненный сценарий, это не случайность.\n\n"
        "Образ внутреннего мужчины часто влияет на то, каких мужчин ты выбираешь, чего ждёшь от отношений и как переживаешь близость.\n\n"
        "Ниже — бесплатное видео, где я простым языком объясняю, кто такой внутренний мужчина и почему эта тема так сильно влияет на личную жизнь."
    )
    keyboard = [
        [InlineKeyboardButton("▶️ Смотреть бесплатное видео", url=config['free_video_url'])],
        [InlineKeyboardButton("🧘 Получить медитацию", callback_data='get_meditation')]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def get_meditation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    query = update.callback_query
    await query.answer()
    set_stage(query.from_user.id, stage='meditation_sent')

    text = (
        "Хорошо, идём глубже 🌿\n\n"
        "Это медитация-встреча с образом внутреннего мужчины. Делай её в спокойной обстановке, лучше в наушниках.\n\n"
        "Не старайся анализировать во время процесса. Просто наблюдай, что приходит: образ, поведение, дистанция, эмоции, ощущения в теле.\n\n"
        "После медитации нажми кнопку ниже и опиши, что увидела. Можно коротко, без длинного рассказа."
    )
    keyboard = [
        [InlineKeyboardButton("🎧 Слушать медитацию", url=config['meditation_url'])],
        [InlineKeyboardButton("📝 Описать образы", callback_data='share_images')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def share_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_stage(query.from_user.id, stage='awaiting_images')
    text = (
        "Напиши мне ответ одним сообщением. Можно коротко.\n\n"
        "1. Кто был этот мужчина\n"
        "2. Как он выглядел или во что был одет\n"
        "3. Как он себя вёл\n"
        "4. Что ты почувствовала рядом с ним\n\n"
        "Если удобнее, можешь ответить буквально в 3–5 фразах."
    )
    await query.edit_message_text(text)
    return ASKING_IMAGES


async def receive_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    user = update.effective_user
    text = update.message.text
    set_stage(user.id, stage='images_received', images=text)

    admin_text = (
        "🔔 Новое описание образов\n\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username if user.username else 'нет'}\n"
        f"chat_id: {user.id}\n\n"
        f"Описание:\n{text}"
    )
    await context.bot.send_message(chat_id=config['admin_chat_id'], text=admin_text)

    keyboard = [[InlineKeyboardButton("📞 Выбрать время для разбора", callback_data='book_call')]]
    await update.message.reply_text(
        "Спасибо, я получил твоё описание.\n\n"
        "Следующий шаг — короткий разбор, где я помогу тебе увидеть смысл этих образов и связать их с твоим сценарием в отношениях.\n\n"
        "Это не просто знакомство. Это встреча, на которой мы разберём твою медитацию, а если тебе откликнется, я расскажу о формате более глубокой индивидуальной работы.\n\n"
        f"{config['price_note']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def book_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    query = update.callback_query
    await query.answer()
    set_stage(query.from_user.id, stage='booking_started')

    if config.get('booking_mode') == 'booking_link':
        text = (
            "Вот ссылка для записи на созвон 📅\n\n"
            "Выбирай удобное время по ссылке. Если слотов не видишь, напиши мне напрямую — добавлю вручную."
        )
        keyboard = [[InlineKeyboardButton("📅 Открыть запись", url=config.get('booking_link'))]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    text = (
        "Ниже твоё свободное расписание для разбора.\n\n"
        "Ты сам вписываешь удобные слоты в файл конфигурации, а бот показывает их клиенту.\n\n"
        f"Доступные окна:\n{next_slots_text(config)}\n\n"
        "Напиши в ответ день и время, например: Среда 15:00"
    )
    await query.edit_message_text(text)
    return ASKING_SLOT


async def receive_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    user = update.effective_user
    chosen = update.message.text.strip()
    set_stage(user.id, stage='slot_requested', chosen_slot=chosen)

    admin_text = (
        "📅 Запрос на созвон\n\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username if user.username else 'нет'}\n"
        f"chat_id: {user.id}\n"
        f"Выбранное время: {chosen}"
    )
    await context.bot.send_message(chat_id=config['admin_chat_id'], text=admin_text)

    await update.message.reply_text(
        "Принято 🙏\n\n"
        "Я получил твой запрос по времени. Скоро подтвержу слот лично сообщением."
    )
    return ConversationHandler.END


async def meditation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    keyboard = [
        [InlineKeyboardButton("🎧 Слушать медитацию", url=config['meditation_url'])],
        [InlineKeyboardButton("📝 Описать образы", callback_data='share_images')]
    ]
    await update.message.reply_text(
        "Вот медитация. После неё опиши образы, и мы пойдём дальше.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def call_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if config.get('booking_mode') == 'booking_link':
        keyboard = [[InlineKeyboardButton("📅 Записаться", url=config.get('booking_link'))]]
        await update.message.reply_text("Вот ссылка для записи на разбор.", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(
            "Свободные окна для созвона:\n\n" + next_slots_text(config) + "\n\nНапиши сюда день и время, которые тебе подходят."
        )


def main():
    config = load_config()
    token = config['bot_token']
    app = Application.builder().token(token).build()

    conv_images = ConversationHandler(
        entry_points=[CallbackQueryHandler(share_images, pattern='share_images')],
        states={ASKING_IMAGES: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_images)]},
        fallbacks=[]
    )

    conv_booking = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_call, pattern='book_call')],
        states={ASKING_SLOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_slot)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('meditation', meditation_command))
    app.add_handler(CommandHandler('call', call_command))
    app.add_handler(CallbackQueryHandler(get_meditation, pattern='get_meditation'))
    app.add_handler(conv_images)
    app.add_handler(conv_booking)

    logger.info('Bot started')
    app.run_polling()


if __name__ == '__main__':
    main()

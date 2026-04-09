Railway deploy
Что загрузить в GitHub
Положи в репозиторий эти файлы:

inner_man_bot.py

bot_config.json

requirements.txt

Procfile

runtime.txt

Как деплоить в Railway
На странице New Project выбери GitHub Repository.

Подключи GitHub, если Railway попросит.

Выбери репозиторий, куда загружены файлы бота.

Railway сам увидит requirements.txt и Procfile.

После первого деплоя открой сервис и проверь логи.

Что обязательно заполнить до деплоя
В bot_config.json замени:

PASTE_YOUR_BOT_TOKEN

PASTE_YOUR_CHAT_ID

PASTE_FREE_VIDEO_URL

PASTE_MEDITATION_URL

Два варианта записи на созвон
1. Ручные слоты
Оставь:

json
"booking_mode": "manual_slots"
И пропиши своё расписание в slots.

2. Через ссылку
Поставь:

json
"booking_mode": "booking_link",
"booking_link": "https://calendly.com/your-link"
Если не хочешь GitHub
Можно выбрать Empty Project, затем добавить сервис из GitHub CLI или через Railway CLI, но через GitHub проще всего.

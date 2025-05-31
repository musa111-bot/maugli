# Telegram Exam Bot

## Как запустить на Render

1. Создай GitHub-репозиторий
2. Залей все файлы из этого проекта в репозиторий
3. Зайди на https://render.com
4. Нажми "New" → "Web Service"
5. Подключи GitHub и выбери репозиторий
6. Настрой:
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
7. В разделе Environment Variables добавь:
   - `BOT_TOKEN`: токен бота
   - `REPORT_CHANNEL_ID`: ID канала (без кавычек)

8. Нажми "Deploy" — бот готов к работе!

import asyncio
import os
import json
import random
from datetime import datetime, timedelta
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook
from dotenv import load_dotenv

# === Load .env ===
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", 0))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", 10000))

# === Timezone ===
bishkek_tz = pytz.timezone("Asia/Bishkek")

# === Telegram setup ===
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# === Load Questions ===
with open("questions.json", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

# === FSM States ===
class ExamState(StatesGroup):
    waiting_for_name = State()
    in_exam = State()

user_data = {}
exam_cooldowns = {}  # user_id: datetime


@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    now = datetime.now(bishkek_tz)

    if user_id in exam_cooldowns and now < exam_cooldowns[user_id]:
        remaining = exam_cooldowns[user_id] - now
        minutes, seconds = divmod(remaining.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        await message.answer(f"❗ Повторная попытка будет доступна через: {hours} ч. {minutes} мин.", parse_mode='HTML')
        return

    await message.answer(
        "🔸 <b>Добро пожаловать на экзамен Маугли!!</b>\n"
        "🧪 Вы пройдёте 15 вопросов по кальянам, табакам и обслуживанию.\n"
        "⏱️ У вас <b>5 минут</b>.\n\n"
        "✍️ Введите <b>своё имя</b>, чтобы начать:",
        parse_mode='HTML'
    )
    await ExamState.waiting_for_name.set()


@dp.message_handler(state=ExamState.waiting_for_name)
async def receive_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()
    selected_questions = random.sample(QUESTIONS, 15)

    user_data[user_id] = {
        "name": name,
        "score": 0,
        "current_q": 0,
        "questions": selected_questions
    }

    await message.answer(f"Спасибо, {name}. Начнём экзамен!")
    await send_question(message.chat.id, user_id)
    await ExamState.in_exam.set()


async def send_question(chat_id, user_id):
    user = user_data[user_id]
    q_index = user["current_q"]
    if q_index >= len(user["questions"]):
        await finish_exam(chat_id, user_id)
        return

    question = user["questions"][q_index]
    buttons = [InlineKeyboardButton(text=ans, callback_data=str(i)) for i, ans in enumerate(question['answers'])]
    markup = InlineKeyboardMarkup(row_width=1).add(*buttons)
    await bot.send_message(chat_id, f"❓ <b>Вопрос {q_index + 1}:</b> {question['question']}", reply_markup=markup, parse_mode='HTML')


@dp.callback_query_handler(state=ExamState.in_exam)
async def answer_question(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = user_data.get(user_id)
    if not data:
        await callback.answer("Сессия истекла. Напишите /start заново.")
        return

    q_index = data["current_q"]
    question = data["questions"][q_index]

    correct_index = question['answers'].index(question['correct'])
    if int(callback.data) == correct_index:
        data["score"] += 1

    data["current_q"] += 1
    await callback.answer()
    await send_question(callback.message.chat.id, user_id)


async def finish_exam(chat_id, user_id):
    data = user_data[user_id]
    name = data["name"]
    score = data["score"]
    total = len(data["questions"])
    status = "✅ Сдал" if score >= 12 else "❌ Не сдал"

    result_text = (
        f"✅ Экзамен завершён!\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"📊 Результат: <b>{score} / {total}</b>\n"
        f"📌 Статус: <b>{status}</b>"
    )
    await bot.send_message(chat_id, result_text, parse_mode='HTML')

    retry_markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔁 Пройти заново (через 2 часа)", callback_data="retry_exam")
    )
    await bot.send_message(chat_id, "Хотите пройти заново?", reply_markup=retry_markup)

    exam_cooldowns[user_id] = datetime.now(bishkek_tz) + timedelta(hours=2)

    if REPORT_CHANNEL_ID:
        now = datetime.now(bishkek_tz)
        timestamp = now.strftime("%d.%m.%Y %H:%M")
        await bot.send_message(REPORT_CHANNEL_ID,
            f"🧪 Экзамен ({timestamp}):\n"
            f"👤 {name}\n"
            f"📝 Результат: {score}/{total}\n"
            f"📌 Статус: {status}"
        )

    user_data.pop(user_id)


@dp.callback_query_handler(lambda c: c.data == "retry_exam")
async def retry_exam(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    now = datetime.now(bishkek_tz)

    if user_id in exam_cooldowns and now < exam_cooldowns[user_id]:
        remaining = exam_cooldowns[user_id] - now
        minutes, seconds = divmod(remaining.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        await callback.answer(f"⏳ Осталось: {hours} ч. {minutes} мин.", show_alert=True)
    else:
        await callback.message.delete()
        await start(callback.message, state=None)


# === Webhook Setup ===
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

# === Start Webhook Server ===
if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host='0.0.0.0',
        port=PORT
    )

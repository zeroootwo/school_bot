import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Добавь в импорты
from school_bot import get_cleaned_schedule, current_lesson, get_week_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
admin_id = int(os.getenv("ADMIN_ID"))
group_id = int(os.getenv("GROUP_ID"))
cancelled_lessons = set()

async def send_morning_schedule():
    logger.info("Запуск ранкової розсилки...")
    try:
        from school_bot import get_week_type
        data = get_cleaned_schedule(days_offset=0)
        if not data:
            return
        week_type = get_week_type()
        week_name = "Чисельник (Верхній тиждень) 🔼" if week_type == "numerator" else "Знаменник (Нижній тиждень) 🔽"
        ua_days = {
            "Monday": "Понеділок", "Tuesday": "Вівторок", "Wednesday": "Середа",
            "Thursday": "Четвер", "Friday": "П'ятниця"
        }
        today_name = ua_days.get(datetime.now().strftime('%A'), "Сьогодні")
        response = f"☀️ **Доброго ранку!**\n"
        response += f"📅 Сьогодні: **{today_name}**, {datetime.now().strftime('%d.%m')}\n"
        response += f"📑 Тиждень: **{week_name}**\n\n"  # ВОТ ЭТА СТРОЧКА
        response += f"📚 Ваш розклад:\n"
        for i, lesson in enumerate(data):
            response += f"{i + 1}. {lesson['time']} — *{lesson['subject']}*\n"
        response += "\nБажаю успіхів! 🍀"
        await bot.send_message(group_id, response, parse_mode="Markdown", disable_notification=True)
        await bot.send_message(admin_id, f"✅ Розсилка на {today_name} ({week_type}) відправлена.")
        logger.info("Ранкова розсилка відправлена ✅")
    except Exception as e:
        logger.error(f":( Помилка розсилки: {e}")

def main_menu(user_id, chat_type):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚀 Що зараз за урок?")
    builder.button(text="🌅 Розклад на завтра")
    builder.button(text="📚 Розклад на сьогодні")
    if user_id == admin_id and chat_type == "private":
        builder.button(text="⚙️ Адмінка")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Оберіть дію 👇")

async def send_or_edit_schedule(message: types.Message, is_callback=False, is_admin_mode=False):
    data = get_cleaned_schedule()
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    today = days[datetime.now().weekday()]
    today_lessons = [l for l in data if l["day"] == today]
    if not today_lessons:
        text = f"📅 Сьогодні {today}, уроків немає!"
        if is_callback:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return
    builder = InlineKeyboardBuilder()
    response = f"📅 *Розклад на сьогодні ({today})*\n\n"
    for i, lesson in enumerate(today_lessons):
        is_cancelled = lesson['subject'] in cancelled_lessons
        status = "❌ (СКАСОВАНО)" if is_cancelled else "✅"
        response += f"{i + 1}. {lesson['time']} — *{lesson['subject']}* {status}\n"
        if is_admin_mode:
            btn_text = "Відновити" if is_cancelled else "Скасувати"
            builder.button(text=f"{btn_text} {lesson['subject']}", callback_data=f"toggle_{i}")
    builder.adjust(1)
    markup = builder.as_markup() if (is_admin_mode and message.chat.type == "private") else None
    if is_callback:
        await message.edit_text(response, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.answer(response, parse_mode="Markdown", reply_markup=markup)

@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    markup = main_menu(message.from_user.id, message.chat.type)
    if message.from_user.id == admin_id:
        await message.answer(f"Вітаю, Командире {message.from_user.first_name}! 🫡✨", reply_markup=markup)
    else:
        await message.answer(f"Привіт, {message.from_user.first_name}! Я твій шкільний помічник.", reply_markup=markup)

@dp.message(F.text == "📚 Розклад на сьогодні")
@dp.message(Command("today"))
async def show_today(message: types.Message):
    await send_or_edit_schedule(message)

@dp.message(F.text == "🚀 Що зараз за урок?")
@dp.message(Command("now"))
async def show_now(message: types.Message):
    data = get_cleaned_schedule()
    current = current_lesson(data)
    if not current:
        await message.answer("☕️ Зараз перерва або уроки закінчились!")
        return
    status = "❌ СКАСОВАНО" if current['subject'] in cancelled_lessons else "✅ ЙДЕ ЗАРАЗ"
    text = (f"🔥 *{current['subject']}* ({status})\n"
            f"⏰ Час: {current['time']}\n"
            f"🔗 [Посилання на Zoom]({current['link']})\n"
            f"🆔 ID: `{current['id']}`\n"
            f"🔑 Код: `{current['code']}`")
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_lesson(callback: types.CallbackQuery):
    if callback.from_user.id != admin_id: return
    idx = int(callback.data.split("_")[1])
    data = get_cleaned_schedule()
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    today = days[datetime.now().weekday()]
    today_lessons = [l for l in data if l["day"] == today]
    lesson_name = today_lessons[idx]['subject']
    if lesson_name in cancelled_lessons:
        cancelled_lessons.remove(lesson_name)
        status_text = f"✅ Урок *{lesson_name}* відновлено!"
    else:
        cancelled_lessons.add(lesson_name)
        status_text = f"❌ Урок *{lesson_name}* скасовано!"
    await callback.answer(status_text)
    await bot.send_message(group_id, status_text, parse_mode="Markdown")
    await send_or_edit_schedule(callback.message, is_callback=True, is_admin_mode=True)

@dp.message(F.text == "⚙️ Адмінка")
async def admin_panel(message: types.Message):
    if message.from_user.id == admin_id and message.chat.type == "private":
        await send_or_edit_schedule(message, is_admin_mode=True)
    else:
        await message.answer("❌ Доступ лише для адміна в особистих повідомленнях.")

@dp.message(F.text == "🌅 Розклад на завтра")
@dp.message(Command("tomorrow"))
async def show_tomorrow_schedule(message: types.Message):
    data = get_cleaned_schedule(days_offset=1)
    if not data:
        await message.answer("🌅 Завтра вихідний! Відпочивай. 😎")
        return
    response = f"🌅 *Розклад на завтра ({data[0]['day']})*\n\n"
    for i, lesson in enumerate(data):
        response += f"{i + 1}. {lesson['time']} — *{lesson['subject']}*\n"
    await message.answer(response, parse_mode="Markdown")

async def main():
    logger.info("Бот починає роботу...")
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    scheduler.add_job(send_morning_schedule, "cron", day_of_week='mon-fri', hour=9, minute=20)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

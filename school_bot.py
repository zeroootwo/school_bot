import re
import os
import gspread
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

load_dotenv()

def current_lesson(schedule):
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    today = days[now.weekday()]
    for lesson in schedule:
        if lesson["day"] == today:
            start_str, end_str = lesson["time"].split("-")
            if start_str.strip() <= current_time <= end_str.strip():
                return lesson
    return None

def get_week_type():
    week_num = datetime.now().isocalendar()[1]
    return "numerator" if week_num % 2 == 0 else "denominator"

def get_cleaned_schedule(days_offset=0):
    try:
        logger.info(f"Запит до Google Таблиці (зміщення: {days_offset} днів)")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("schoolbot.json", scope)
        client = gspread.authorize(creds)
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        sheet = client.open_by_key(sheet_id).sheet1
        raw_data = sheet.get_all_values()
        logger.info(f"Дані з таблиці отримано. Всього рядків: {len(raw_data)}")
        schedule = []
        days_list = ["ПОНЕДІЛОК", "ВІВТОРОК", "СЕРЕДА", "ЧЕТВЕР", "П’ЯТНИЦЯ", "П'ЯТНИЦЯ"]
        target_date = datetime.now().date() + timedelta(days=days_offset)
        weekday = target_date.weekday()
        if weekday > 4: return []
        target_map = {0: "ПОНЕДІЛОК", 1: "ВІВТОРОК", 2: "СЕРЕДА", 3: "ЧЕТВЕР", 4: "П’ЯТНИЦЯ"}
        target_day = target_map.get(weekday)
        is_collecting = False
        for row in raw_data:
            if not row: continue
            cell_a = str(row[0]).strip().upper()
            if is_collecting and any(d in cell_a for d in days_list if d != target_day):
                break
            if is_collecting and "КОДИ" in cell_a:
                break
            if target_day in cell_a:
                is_collecting = True
            if is_collecting and len(row) > 3 and ":" in str(row[2]):
                subject = row[3].strip()
                if not subject: continue
                lesson_time = row[2].strip()
                lesson_num = str(row[1]).strip()

                if target_day == "ПОНЕДІЛОК" and lesson_num == "7":
                    lesson_time = "08:45-09:30"
                zoom_info = row[6].strip() if len(row) > 6 else ""
                clean_info = re.sub(r'\s+', ' ', zoom_info).strip()
                parts = clean_info.split()
                m_id, m_code = "Не вказано", "Не вказано"
                if len(parts) >= 4:
                    m_id = f"{parts[0]} {parts[1]} {parts[2]}"
                    m_code = parts[3]
                elif len(parts) == 2:
                    m_id, m_code = parts[0], parts[1]
                schedule.append({
                    "day": target_day.capitalize().replace("П’ятниця", "П'ятниця"),
                    "time": lesson_time,
                    "subject": subject,
                    "link": row[5] if len(row) > 5 else "Нема посилання",
                    "id": m_id,
                    "code": m_code
                })
        schedule.sort(key=lambda x: x['time'].split('-')[0].strip().zfill(5))
        logger.info(f"Обробка завершена. Знайдено {len(schedule)} уроків.")
        return schedule
    except Exception as e:
        logger.error(f"ПОМИЛКА при роботі з Google Таблицею: {e}")
        return []

if __name__ == "__main__":
    pass

import re
import os
import gspread
import logging
import pytz
from dotenv import load_dotenv
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

load_dotenv()

def current_lesson(schedule):
    kiev_tz = pytz.timezone('Europe/Kiev')
    now = datetime.now(kiev_tz)
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
    kiev_tz = pytz.timezone('Europe/Kiev')
    now = datetime.now(kiev_tz)
    week_num = now.isocalendar()[1]
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
        week_num = target_date.isocalendar()[1]
        week_type = "denominator" if week_num % 2 != 0 else "numerator"
        is_collecting = False
        last_valid_time = ""
        last_valid_num = ""
        for row in raw_data:
            if not row: continue
            cell_a = str(row[0]).strip().upper()
            if any(d in cell_a for d in days_list if d != target_day):
                if is_collecting: break
            if "КОДИ" in cell_a and is_collecting:
                break
            if target_day in cell_a:
                is_collecting = True
                last_valid_time = ""
            if is_collecting and len(row) > 3:
                raw_time = str(row[2]).strip()
                if ":" in raw_time:
                    current_lesson_time = raw_time
                    last_valid_time = raw_time
                    if str(row[1]).strip(): last_valid_num = str(row[1]).strip()
                elif last_valid_time and row[3].strip():
                    current_lesson_time = last_valid_time
                else:
                    continue
                subject = row[3].strip()
                if not subject: continue
                week_marker = row[7].strip().lower() if len(row) > 7 else ""
                if "чис" in week_marker and week_type == "denominator":
                    continue
                if "зн" in week_marker and week_type == "numerator":
                    continue
                lesson_num = str(row[1]).strip()
                if not lesson_num and last_valid_num: lesson_num = last_valid_num
                if target_day == "ПОНЕДІЛОК" and lesson_num == "7":
                    current_lesson_time = "08:45-09:30"
                zoom_info = row[6].strip() if len(row) > 6 else ""
                clean_info = re.sub(r'\s+', ' ', zoom_info).strip()
                parts = clean_info.split()
                m_id = "Не вказано"
                m_code = "Не вказано"
                if len(parts) == 1:
                    m_id = parts[0]
                elif len(parts) == 2:
                    m_id, m_code = parts[0], parts[1]
                elif len(parts) >= 3:
                    if len(parts) == 3 and all(p.isdigit() for p in parts):
                        m_id = " ".join(parts)
                    else:
                        m_code = parts[-1]
                        m_id = " ".join(parts[:-1])
                schedule.append({
                    "day": target_day.capitalize().replace("П’ятниця", "П'ятниця"),
                    "time": current_lesson_time,
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

def get_classroom_codes_dict():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("schoolbot.json", scope)
        client = gspread.authorize(creds)
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        sheet = client.open_by_key(sheet_id).worksheet("Коди та посилання")
        data = sheet.get_all_values()
        result = []
        for row in data:
            if len(row) >= 2 and row[1] and row[1] not in ["Код Google Classroom", ""]:
                subject_full = row[0].strip()
                subject_short = subject_full.split('(')[0].strip()
                result.append({
                    "name": subject_short, 
                    "code": row[1].strip()
                })
        result.sort(key=lambda x: x['name'])
        return result
    except Exception as e:
        logger.error(f"Помилка отримання кодів: {e}")
        return []

if __name__ == "__main__":
    pass

import pymysql
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, timedelta

load_dotenv()

# Московский часовой пояс
MOSCOW_TZ = timezone(timedelta(hours=3))

def get_moscow_time():
    """Возвращает текущее московское время"""
    return datetime.now(MOSCOW_TZ)

def get_moscow_date():
    """Возвращает текущую московскую дату"""
    return get_moscow_time().date()

def get_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
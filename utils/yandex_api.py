import aiohttp
import logging
import time
import csv
import io
import os
from datetime import datetime
from utils.db_utils import get_user

# Импортируйте ваши настройки
YANDEX_METRICA_ID = '106309492'
YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN", "")

logger = logging.getLogger(__name__)

class YandexMetricaService:
    def __init__(self, token: str, counter_id: int):
        self.token = token
        self.counter_id = counter_id
        self.base_url = "https://api-metrica.yandex.net/management/v1"

    async def upload_conversion(self, client_id: str, goal_name: str, price: float = 0, user_id: int = None):
        """
        Загрузка оффлайн-конверсии через официальный API (OAuth).
        """
        logger.info(f"📤 upload_conversion: client_id={client_id}, goal={goal_name}, price={price}")
         
        if not self.token:
            logger.error("❌ Нет YANDEX_OAUTH_TOKEN. Не могу загрузить конверсию.")
            return

        # 1. Формируем CSV данные
        current_time = int(time.time())
        user = await get_user(user_id)
        if user:
            client_id = user.get('ym_client_id', None)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ClientId', 'Target', 'DateTime', 'Price', 'Currency'])
        writer.writerow([str(client_id), goal_name, current_time, price, 'RUB'])
        
        csv_data = output.getvalue()
        
        url = f"{self.base_url}/counter/{self.counter_id}/offline_conversions/upload"
        
        params = {
            "client_id_type": "CLIENT_ID",
            "comment": "Telegram Bot Conversion"
        }
        
        headers = {
            "Authorization": f"OAuth {self.token}",
        }

        data = aiohttp.FormData()
        data.add_field('file', csv_data, filename='conversions.csv', content_type='text/csv')

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params, headers=headers, data=data) as resp:
                    resp_text = await resp.text()
                    
                    logger.info(f"📥 Метрика ответ (status={resp.status}):")
                    logger.info(f"   {resp_text[:500]}")
                    
                    if resp.status == 200:
                        try:
                            resp_json = await resp.json()
                            logger.info(f"✅ Конверсия загружена. Response: {resp_json}")
                        except:
                            logger.info(f"✅ Конверсия загружена (не JSON): {resp_text[:200]}")
                    else:
                        logger.error(f"❌ Ошибка API Метрики {resp.status}: {resp_text}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка соединения с Метрикой: {e}")
            import traceback
            logger.error(traceback.format_exc())

            
    async def send_hit_fast(self, client_id: str, goal_name: str):
        """
        МГНОВЕННАЯ отправка (эмуляция реального браузера).
        """
        url = f"https://mc.yandex.ru/watch/{self.counter_id}"
        
        # Виртуальная страница
        page_url = f"goal://{goal_name}"
        
        params = {
            "page-url": page_url,
            "page-ref": "app:/telegram_bot",
            "client-id": str(client_id),
            "browser-info": "cp:1:ar:1:uid:0:hu:1", # Добавил флагов (cookies enabled, etc)
            "charset": "utf-8",
            "is-b": "0", # Якобы не робот
            "wmode": "0",
        }
        
        # 1. ОБЯЗАТЕЛЬНО: User-Agent реального Chrome
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        
        # 2. Cookies
        cookies = {
            "_ym_uid": str(client_id),
            "_ym_d": str(int(time.time())), # Дата первого визита
            "_ym_isad": "2",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, cookies=cookies, headers=headers) as resp:
                    if resp.status == 200:
                        logger.info(f"🚀 Хит '{goal_name}' отправлен (с маскировкой под Chrome)")
                    else:
                        logger.warning(f"⚠️ Хит не принят: {resp.status}")
        except Exception as e:
            logger.error(f"❌ Ошибка Fast Hit: {e}")

# Создаем глобальный экземпляр
metrica = YandexMetricaService(token=YANDEX_OAUTH_TOKEN, counter_id=YANDEX_METRICA_ID)
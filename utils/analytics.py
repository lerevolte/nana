import aiohttp
import logging
import asyncio
import time
import random

logger = logging.getLogger(__name__)

COUNTER_ID = 106309492

async def send_yandex_goal(client_id: str, goal_name: str, user_ip: str = None):
    """
    Отправляет цель в Яндекс.Метрику через серверный запрос (Virtual Pageview).
    
    :param client_id: _ym_uid (ClientID метрики), полученный от пользователя
    :param goal_name: Название цели (например, 'podpiska-na-bota')
    :param user_ip: IP пользователя (необязательно, но полезно для гео)
    """
    if not client_id:
        # Если client_id нет, генерируем временный, но лучше сохранять реальный с сайта
        # Формат Yandex: timestamp + random
        client_id = f"{int(time.time())}{random.randint(100000000, 999999999)}"

    url = f"https://mc.yandex.ru/watch/{COUNTER_ID}"
    
    # Мы эмулируем посещение страницы с адресом goal://название_цели
    # Это стандартная практика для server-side событий
    page_url = f"goal://{goal_name}"
    
    params = {
        "page-url": page_url,
        "page-ref": "app:/telegram_bot", # Реферер
        "client-id": client_id,          # ID пользователя (обязательно!)
        "browser-info": "cp:1",          # Кодировка (cp:1 = utf-8)
        "charset": "utf-8"
    }
    
    # Важно передать Cookie _ym_uid, чтобы Метрика склеила сессию
    cookies = {
        "_ym_uid": client_id
    }
    
    # Если есть IP, можно попробовать передать через заголовки (Yandex может игнорировать)
    headers = {
        "User-Agent": "TelegramBot/1.0 (Python)"
    }
    if user_ip:
        headers["X-Forwarded-For"] = user_ip

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, cookies=cookies, headers=headers) as resp:
                if resp.status == 200:
                    logging.info(f"✅ Цель {goal_name} отправлена в Метрику (cid: {client_id})")
                else:
                    logging.warning(f"⚠️ Ошибка отправки цели в Метрику: {resp.status}")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки цели: {e}")

async def send_analytics(user_id: int, start_param: str = None):
    if not COUNTER_ID:
        logger.warning("YANDEX_METRICA_ID not set in config!")
        return

    # 1. Используем реальный, валидный URL. 
    # Метрика может игнорировать странные протоколы.
    page_url = "https://t.me/ne_davinci_bot"  # Замените на юзернейм вашего бота
    
    if start_param:
        # Используем стандартную метку utm_source
        page_url += f"?utm_source={start_param}"

    # 2. Максимально похожие на браузер заголовки
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    params = {
        "tid": COUNTER_ID,
        "cid": str(user_id),      # Client ID
        "url": page_url,          # URL визита
        "ua": headers["User-Agent"],
        "lang": "ru"
    }

    logger.info(f"📤 Sending analytics to Yandex: {page_url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://mc.yandex.ru/watch", # Используем эндпоинт без ID в пути (универсальный)
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Analytics SENT for {user_id}. Status: 200")
                else:
                    logger.error(f"❌ Analytics FAILED. Status: {response.status}")
                    # Если ошибка, выведем текст ответа для понимания
                    text = await response.text()
                    logger.error(f"Response: {text}")
                    
    except Exception as e:
        logger.error(f"❌ Analytics EXCEPTION: {e}")
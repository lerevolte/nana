import requests
import base64
import logging
import time
from io import BytesIO
import os
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)

SEGMIND_API_KEY = os.getenv('SEGMIND_API_TOKEN')
SEGMIND_BASE_URL = "https://api.segmind.com/v1"


class SegmindError(Exception):
    """Ошибка Segmind API"""
    def __init__(self, user_message: str, technical_message: str = None):
        self.user_message = user_message
        self.technical_message = technical_message or user_message
        super().__init__(self.technical_message)


def is_segmind_available() -> bool:
    """Проверяет, доступен ли Segmind API"""
    return SEGMIND_API_KEY is not None and len(SEGMIND_API_KEY) > 0


def get_credits() -> dict:
    """
    Получает информацию о кредитах пользователя.
    Возвращает dict с полями credits и free-credits.
    """
    if not is_segmind_available():
        return {"error": "Segmind API не настроен"}
    
    try:
        response = requests.get(
            f"{SEGMIND_BASE_URL}/get-user-credits",
            headers={"x-api-key": SEGMIND_API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
    
    except Exception as e:
        logger.error(f"[Segmind] Error getting credits: {e}")
        return {"error": str(e)}


def _get_headers() -> dict:
    """Возвращает заголовки для запросов"""
    return {
        "x-api-key": SEGMIND_API_KEY,
        "Content-Type": "application/json"
    }


def _download_image_from_url(url: str) -> BytesIO:
    """Скачивает изображение по URL"""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    result = BytesIO(response.content)
    result.name = "result.png"
    return result


def _process_response(response: requests.Response) -> BytesIO:
    """Обрабатывает ответ от Segmind API"""
    if response.status_code != 200:
        error_text = response.text
        logger.error(f"[Segmind] API Error {response.status_code}: {error_text}")
        
        if response.status_code == 429:
            raise SegmindError(
                user_message="😔 Сервис временно перегружен. Попробуйте через минуту.",
                technical_message=f"Rate limit: {error_text}"
            )
        elif response.status_code == 402:
            raise SegmindError(
                user_message="😔 Сервис временно перегружен. Попробуйте через минуту.",
                technical_message=f"Insufficient credits: {error_text}"
            )
        else:
            raise SegmindError(
                user_message="😔 Ошибка генерации. Попробуйте позже.",
                technical_message=f"HTTP {response.status_code}: {error_text}"
            )
    
    content_type = response.headers.get('Content-Type', '')
    logger.info(f"[Segmind] Response Content-Type: {content_type}")
    
    # Если ответ — изображение напрямую (бинарные данные)
    if 'image/' in content_type or content_type.startswith('image'):
        buffer = BytesIO(response.content)
        buffer.name = "result.png"
        return buffer
    
    # Если ответ — JSON
    if 'application/json' in content_type:
        try:
            result = response.json()
            
            if isinstance(result, dict):
                # --- ПРОВЕРКА НА ТЕКСТОВЫЙ ОТВЕТ (Gemini) ---
                if "data" in result and isinstance(result["data"], dict):
                    data = result["data"]
                    if "message" in data and "image" not in data:
                        msg = data["message"]
                        logger.warning(f"[Segmind] Model returned text: {msg}")
                        
                        # Если сработал фильтр безопасности — не повторяем попытки
                        if any(x in msg.lower() for x in ['nsfw', 'safety', 'unsafe', 'policy']):
                            raise SegmindError(
                                user_message="🔞 <b>Контент заблокирован фильтром безопасности.</b>\nПопробуйте изменить запрос.",
                                technical_message=f"Safety filter: {msg}"
                            )
                        
                        # В остальных случаях повторяем
                        raise ValueError(f"Model returned text instead of image: {msg}")
                # --------------------------------------------

                # Проверяем успешные ключи
                if "image" in result:
                    image_data = base64.b64decode(result["image"])
                    buffer = BytesIO(image_data)
                    buffer.name = "result.png"
                    return buffer
                elif "data" in result and "image" in result["data"]:
                     # Google/Nano формат с картинкой
                    image_data = base64.b64decode(result["data"]["image"])
                    buffer = BytesIO(image_data)
                    buffer.name = "result.png"
                    return buffer
                elif "image_url" in result:
                    return _download_image_from_url(result["image_url"])
                elif "url" in result:
                    return _download_image_from_url(result["url"])
                elif "output" in result:
                    return _download_image_from_url(result["output"])
            
            elif isinstance(result, str):
                if result.startswith("http"):
                    return _download_image_from_url(result)
                else:
                    image_data = base64.b64decode(result)
                    buffer = BytesIO(image_data)
                    buffer.name = "result.png"
                    return buffer
            
            elif isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if isinstance(first_item, str) and first_item.startswith("http"):
                    return _download_image_from_url(first_item)
                elif isinstance(first_item, dict) and "url" in first_item:
                    return _download_image_from_url(first_item["url"])
                    
        except SegmindError:
            raise
        except Exception as e:
            # Любая ошибка парсинга JSON должна вызывать retry
            logger.error(f"[Segmind] JSON parse error/Unexpected format: {e}")
            raise ValueError(f"Invalid JSON response: {e}")
    
    # 3. Fallback: Пробуем как бинарные данные, даже если заголовок кривой
    if len(response.content) > 1000:
        content = response.content
        if content[:4] == b'\x89PNG' or content[:2] == b'\xff\xd8':
            buffer = BytesIO(content)
            buffer.name = "result.png"
            return buffer
    
    # Если ничего не подошло — это ошибка, требующая повтора
    raise ValueError(f"Unexpected response format. Content-Type: {content_type}, Length: {len(response.content)}")


def _bytes_to_base64(image_bytes: bytes) -> str:
    """Конвертирует bytes в чистый base64"""
    return base64.b64encode(image_bytes).decode('utf-8')

# ============ МАППИНГ МОДЕЛЕЙ ============

# Соответствие внутренних ID моделей эндпоинтам Segmind
MODEL_ENDPOINTS = {
    'google/nano-banana': 'nano-banana',
    'google/nano-banana-pro': 'nano-banana-pro',
    'bytedance/seedream-4': 'seedream-4.5',
    'ideogram-ai/ideogram-v2': 'ideogram-3',
    'recraft-ai/recraft-v3': 'recraft-v3',
    'black-forest-labs/flux-1.1-pro': 'flux-2-pro',
    'stability-ai/stable-diffusion-3.5-large': 'stable-diffusion-3.5-large-txt2img',
}

# Модели, поддерживающие image_urls/image_input
MODELS_WITH_IMAGE_INPUT = ['nano-banana', 'nano-banana-pro', 'seedream-4.5', 'flux-2-pro']


def _get_endpoint(model: str) -> str:
    """Возвращает эндпоинт Segmind для модели"""
    return MODEL_ENDPOINTS.get(model, 'nano-banana-pro')


def _build_generation_payload(model: str, prompt: str, aspect_ratio: str, image_urls: list = None) -> dict:
    endpoint = _get_endpoint(model)
    
    # 1. Модели, понимающие стандартный aspect_ratio (1:1, 16:9 и т.д.)
    if endpoint in ['nano-banana', 'nano-banana-pro', 'seedream-4.5']:
        data = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio
        }
        
        # Параметр output_format добавляем ТОЛЬКО для моделей, которые его поддерживают (Google Nano)
        if "nano" in endpoint:
            data["output_format"] = "png"
            
        if image_urls:
            # Для Nano используем image_urls, для Seedream - image_input
            data["image_urls" if "nano" in endpoint else "image_input"] = image_urls
            
        return data

    # 2. Ideogram (требует формат 1x1 вместо 1:1)
    if endpoint == 'ideogram-3':
        return {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio.replace(":", "x"),
            "style_type": "GENERAL"
        }



    # 3. Модели, требующие точные пиксели (Flux, SD 3.5, Recraft)
    size_map = {
        '1:1': (1024, 1024),
        '16:9': (1365, 768),
        '9:16': (768, 1365),
        '4:3': (1182, 886),
        '3:4': (886, 1182),
        '21:9': (1536, 640)
    }
    w, h = size_map.get(aspect_ratio, (1024, 1024))

    if endpoint == 'flux-2-pro':
        width, height = size_map.get(aspect_ratio, (1024, 1024))
        data = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "safety_tolerance": 3,
            "output_format": "png"
        }
        # ДОБАВЬТЕ ЭТИ СТРОКИ:
        if image_urls:
            # Для Flux на Segmind обычно используется image_prompt или image_input
            # В зависимости от конкретного эндпоинта. 
            # Попробуем стандартный для вашего кода вариант:
            data["image_urls"] = image_urls 
        return data
    
    if endpoint == 'recraft-v3':
        # Список строго разрешенных размеров для Recraft V3
        size_map = {
            '1:1': '1024x1024',
            '16:9': '1820x1024',  # Было 1365x1024, что вызывало ошибку
            '9:16': '1024x1820',
            '4:3': '1365x1024',
            '3:4': '1024x1365',
            '3:2': '1536x1024',
            '2:3': '1024x1536'
        }
        size = size_map.get(aspect_ratio, '1024x1024')
        return {
            "prompt": prompt,
            "size": size,
            "style": "any"
        }

    if endpoint == 'stable-diffusion-3.5-large-txt2img':
        # Вместо ручного расчета пикселей используем прямые пресеты модели
        # Это гарантирует, что формат 16:9 применится корректно
        return {
            "prompt": prompt,
            "negative_prompt": "low quality, blurry, distorted, messy, bad anatomy",
            "steps": 30,              # Увеличиваем шаги для лучшей детализации
            "guidance_scale": 7.5,     # Увеличиваем с 5.5 для точного следования промпту
            "sampler": "euler",
            "scheduler": "simple",
            "aspect_ratio": aspect_ratio if aspect_ratio != "custom" else "1:1",
            "batch_size": 1,
            "image_format": "png",
            "image_quality": 95,
            "base64": False
        }

    return {"prompt": prompt, "aspect_ratio": aspect_ratio}


def generate_image_segmind(prompt: str, aspect_ratio: str = "1:1", model: str = "google/nano-banana-pro", retries: int = 3) -> BytesIO:
    """
    Генерирует изображение через Segmind API.
    Повторяет запрос при получении текста вместо картинки или ошибках сети.
    """
    if not is_segmind_available():
        raise SegmindError(
            user_message="😔 Сервис генерации не настроен.",
            technical_message="Segmind API key not configured"
        )
    
    endpoint = _get_endpoint(model)
    url = f"{SEGMIND_BASE_URL}/{endpoint}"
    payload = _build_generation_payload(model, prompt, aspect_ratio)
    
    logger.info(f"[Segmind] Generating with {endpoint}, aspect_ratio={aspect_ratio}")
    
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=300
            )
            
            return _process_response(response)
            
        except SegmindError:
            # Фатальные ошибки (нет денег, лимиты) выбрасываем сразу
            raise
        except Exception as e:
            # Ошибки сети, битый JSON, текст вместо картинки — повторяем
            last_error = e
            logger.warning(f"[Segmind] Attempt {attempt + 1}/{retries} failed: {e}")
            
            if attempt < retries - 1:
                time.sleep(2)
    
    raise SegmindError(
        user_message="😔 Не удалось сгенерировать изображение после нескольких попыток.",
        technical_message=f"Generation failed after {retries} attempts: {last_error}"
    )

def edit_image_segmind(prompt: str, image_bytes: bytes, model: str = "google/nano-banana-pro", retries: int = 3) -> BytesIO:
    """
    Редактирует изображение через Segmind API.
    Автоматически сохраняет пропорции входного изображения.
    """
    if not is_segmind_available():
        raise SegmindError(
            user_message="😔 Сервис редактирования не настроен.",
            technical_message="Segmind API key not configured"
        )
    
    # 1. Вычисляем пропорции исходного изображения
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        ratio = width / height
        
        # Список поддерживаемых форматов
        ratios = {
            "1:1": 1.0,
            "16:9": 1.777,
            "9:16": 0.562,
            "4:3": 1.333,
            "3:4": 0.75,
            "3:2": 1.5,
            "2:3": 0.666,
            "21:9": 2.333
        }
        # Находим самый близкий формат к формату пользователя
        aspect_ratio = min(ratios.keys(), key=lambda k: abs(ratios[k] - ratio))
        logger.info(f"[Edit] Image size: {width}x{height} ({ratio:.2f}). Selected ratio: {aspect_ratio}")
        
    except Exception as e:
        logger.warning(f"Could not determine aspect ratio: {e}")
        aspect_ratio = "1:1"

    # Загружаем изображение на хостинг
    try:
        from utils.image_hosting import upload_image
        image_url = upload_image(image_bytes)
    except Exception as e:
        raise SegmindError(
            user_message="😔 Не удалось загрузить изображение.",
            technical_message=f"Image upload failed: {e}"
        )
    
    endpoint = _get_endpoint(model)
    
    # Только некоторые модели поддерживают редактирование
    if endpoint not in MODELS_WITH_IMAGE_INPUT:
        endpoint = 'nano-banana-pro'
        model = 'google/nano-banana-pro'
    
    url = f"{SEGMIND_BASE_URL}/{endpoint}"
    
    # Передаем вычисленный aspect_ratio вместо жесткого "match_input_image" или "1:1"
    payload = _build_generation_payload(model, prompt, aspect_ratio, image_urls=[image_url])
    
    # ВАЖНО: Мы удалили блок, который принудительно ставил 1:1
    # if "aspect_ratio" in payload:
    #     payload["aspect_ratio"] = "1:1"
    
    logger.info(f"[Segmind] Editing with {endpoint}, ratio: {aspect_ratio}")
    
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=300 # Увеличенный таймаут
            )
            
            return _process_response(response)
            
        except SegmindError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Segmind] Edit attempt {attempt + 1}/{retries} failed: {e}")
            
            if attempt < retries - 1:
                time.sleep(2)
    
    raise SegmindError(
        user_message="😔 Не удалось отредактировать изображение. Попробуйте позже.",
        technical_message=f"Edit failed after {retries} attempts: {last_error}"
    )
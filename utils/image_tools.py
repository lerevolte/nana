# utils/image_tools.py

import requests
import base64
from io import BytesIO
import time
import logging
from PIL import Image
from utils.image_hosting import upload_image

logger = logging.getLogger(__name__)

def _compress_and_get_original_url(image_bytes: bytes, max_size_mb: float = 9.0) -> tuple[BytesIO, str]:
    """
    Сжимает изображение для Telegram и возвращает ссылку на оригинал.
    
    Returns:
        (compressed_image, original_url)
    """
    # Загружаем оригинал на хостинг (30 минут жизни)
    original_url = upload_image(image_bytes, expiration=1800)
    
    # Сжимаем для Telegram
    compressed = _compress_image(image_bytes, max_size_mb)
    
    return compressed, original_url

def _compress_image(image_bytes: bytes, max_size_mb: float = 9.0, max_dimension: int = 4096) -> BytesIO:
    """
    Сжимает изображение и ограничивает его физические размеры.
    """
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    img = Image.open(BytesIO(image_bytes))
    width, height = img.size

    # Обязательное уменьшение сторон, если они превышают max_dimension
    if width > max_dimension or height > max_dimension:
        ratio = min(max_dimension / width, max_dimension / height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.info(f"[Compress] Resized from {width}x{height} to {new_size[0]}x{new_size[1]}")
    
    # Конвертируем в RGB для JPEG, если нужно
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Проверяем вес и сохраняем
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=90, optimize=True)
    
    if buffer.tell() > max_size_bytes:
        # Если всё ещё тяжелое, пробуем снизить качество
        for quality in [75, 60, 45]:
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            if buffer.tell() <= max_size_bytes:
                break

    buffer.seek(0)
    buffer.name = "result.jpg"
    return buffer

def _compress_and_get_original_url(image_bytes: bytes, max_size_mb: float = 9.0) -> tuple:
    """
    Сжимает изображение для Telegram и возвращает ссылку на оригинал.
    
    Returns:
        (compressed_image, original_url)
    """
    from utils.image_hosting import upload_image
    
    # Загружаем оригинал на хостинг (30 минут жизни)
    original_url = upload_image(image_bytes, expiration=1800)
    
    # Сжимаем для Telegram
    compressed = _compress_image(image_bytes, max_size_mb)
    
    return compressed, original_url


class ToolError(Exception):
    """Ошибка инструмента с понятным сообщением для пользователя"""
    def __init__(self, user_message: str, technical_message: str = None):
        self.user_message = user_message
        self.technical_message = technical_message or user_message
        super().__init__(self.technical_message)


def _get_segmind_config():
    """Получает конфигурацию Segmind"""
    from utils.segmind_service import SEGMIND_API_KEY, SEGMIND_BASE_URL, is_segmind_available
    return SEGMIND_API_KEY, SEGMIND_BASE_URL, is_segmind_available()


def _get_headers():
    """Возвращает заголовки для запросов"""
    api_key, _, _ = _get_segmind_config()
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }


def _get_segmind_config():
    """Получает конфигурацию Segmind"""
    from utils.segmind_service import SEGMIND_API_KEY, SEGMIND_BASE_URL, is_segmind_available
    return SEGMIND_API_KEY, SEGMIND_BASE_URL, is_segmind_available()


def _get_headers():
    """Возвращает заголовки для запросов"""
    api_key, _, _ = _get_segmind_config()
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }


def _bytes_to_base64(image_bytes: bytes) -> str:
    """Конвертирует bytes в чистый base64"""
    return base64.b64encode(image_bytes).decode('utf-8')


def _upload_image(image_bytes: bytes) -> str:
    """Загружает изображение и возвращает публичный URL"""
    from utils.image_hosting import upload_image
    return upload_image(image_bytes)


def _upload_images(images_bytes: list) -> list:
    """Загружает несколько изображений и возвращает список URL"""
    from utils.image_hosting import upload_multiple_images
    return upload_multiple_images(images_bytes)




def _process_segmind_response(response: requests.Response, operation: str) -> BytesIO:
    """Обрабатывает ответ от Segmind API"""
    if response.status_code != 200:
        error_text = response.text
        logger.error(f"[{operation}] API Error {response.status_code}: {error_text}")
        
        if response.status_code == 429:
            raise ToolError(
                user_message="😔 Сервис временно перегружен. Попробуйте через минуту.",
                technical_message=f"Rate limit: {error_text}"
            )
        elif response.status_code == 402:
            raise ToolError(
                user_message="😔 Недостаточно кредитов. Обратитесь к администратору.",
                technical_message=f"Insufficient credits: {error_text}"
            )
        else:
            raise ToolError(
                user_message="😔 Ошибка обработки. Попробуйте позже.",
                technical_message=f"HTTP {response.status_code}: {error_text}"
            )
    
    content_type = response.headers.get('Content-Type', '')
    
    # Бинарные данные изображения
    if 'image/' in content_type:
        buffer = BytesIO(response.content)
        buffer.name = "result.png"
        return buffer
    
    # JSON ответ
    if 'application/json' in content_type:
        try:
            result = response.json()
            
            if isinstance(result, dict):
                if "image" in result:
                    image_data = base64.b64decode(result["image"])
                    buffer = BytesIO(image_data)
                    buffer.name = "result.png"
                    return buffer
                elif "image_url" in result:
                    return _download_image(result["image_url"])
                elif "url" in result:
                    return _download_image(result["url"])
                elif "output" in result:
                    return _download_image(result["output"])
        except Exception as e:
            logger.error(f"[{operation}] Error parsing JSON: {e}")
    
    # Fallback — пробуем как бинарные данные
    if len(response.content) > 1000:
        content = response.content
        if content[:4] == b'\x89PNG' or content[:2] == b'\xff\xd8':
            buffer = BytesIO(content)
            buffer.name = "result.png"
            return buffer
    
    raise ToolError(
        user_message="😔 Неожиданный ответ от сервиса.",
        technical_message=f"Unexpected response format for {operation}"
    )


def _download_image(url: str, retries: int = 3) -> BytesIO:
    """Скачивает изображение по URL"""
    last_error = None
    
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            result = BytesIO(response.content)
            result.name = "result.png"
            return result
            
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось загрузить результат.",
        technical_message=f"Download failed: {last_error}"
    )


# ============ УДАЛЕНИЕ ФОНА ============

def remove_background(image_bytes: bytes, retries: int = 3) -> BytesIO:
    """
    Удаляет фон с изображения через Segmind.
    """
    _, base_url, available = _get_segmind_config()
    
    if not available:
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    url = f"{base_url}/bg-removal"
    image_base64 = _bytes_to_base64(image_bytes)
    
    payload = {
        "image": image_base64
    }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[RemoveBG] Attempt {attempt + 1}/{retries}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=60
            )
            
            return _process_segmind_response(response, "RemoveBG")
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[RemoveBG] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось удалить фон. Попробуйте позже.",
        technical_message=f"RemoveBG failed after {retries} attempts: {last_error}"
    )

# ============ АПСКЕЙЛ ============

def upscale_image(image_bytes: bytes, scale: int = 2, retries: int = 3) -> tuple:
    """
    Увеличивает разрешение изображения через Segmind.
    
    Returns:
        (compressed_image, original_url) - сжатое изображение и ссылка на оригинал
    """
    _, base_url, available = _get_segmind_config()
    
    if not available:
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    url = f"{base_url}/esrgan"
    image_base64 = _bytes_to_base64(image_bytes)
    
    payload = {
        "image": image_base64,
        "scale": scale
    }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[Upscale] Attempt {attempt + 1}/{retries}, scale={scale}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=120
            )
            
            result = _process_segmind_response(response, "Upscale")
            result.seek(0)
            result_bytes = result.read()

            # Загружаем оригинал на хостинг
            from utils.image_hosting import upload_image
            original_url = upload_image(result_bytes, expiration=1800)

            # Проверяем физические размеры результата
            img = Image.open(BytesIO(result_bytes))
            width, height = img.size

            # Если любая сторона больше 10 000 px, Telegram точно выдаст ошибку Dimensions.
            # В этом случае возвращаем None вместо сжатого файла.
            if width > 10000 or height > 10000:
                logger.warning(f"[Upscale] Image is too large for TG ({width}x{height}). Sending link only.")
                return None, original_url

            # В остальных случаях пытаемся сжать до 4096px для отправки превью
            compressed = _compress_image(result_bytes, max_dimension=4096)
            return compressed, original_url
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Upscale] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось улучшить качество. Попробуйте позже.",
        technical_message=f"Upscale failed after {retries} attempts: {last_error}"
    )


# ============ СТИЛИЗАЦИЯ ============

# ============ СТИЛИЗАЦИЯ (ОБНОВЛЕНО) ============

STYLE_PROMPTS = {
    # 1. АНИМАЦИЯ И РИСУНОК
    "anime": "Transform into high-quality anime art style. Detailed cel shading, vibrant colors, expressive anime eyes, clean lines, Japanese animation aesthetic like Makoto Shinkai backgrounds. REMOVE photorealism.",
    
    "cartoon": "Transform into a 2D vector cartoon. Flat design, thick bold outlines, solid bright colors. Style like Gravity Falls or Rick and Morty. NO shading, NO gradients, purely flat cartoon look.",
    
    "sketch": "Transform into a rough pencil sketch on paper. Black graphite lines on white background, messy hatching, artistic shading. Hand-drawn look, unfinished edges. Monochrome.",
    
    "comic": "Transform into a vintage American comic book style. Bold black ink outlines, visible Ben-Day dots (halftone pattern), limited color palette (cyan, magenta, yellow), dramatic shadows, speech bubble aesthetic.",

    # 2. ХУДОЖЕСТВЕННЫЕ
    "painting": "Transform into a classical oil painting on canvas. Visible thick brushstrokes (impasto), textured canvas look, rich deep colors. Style of Impressionism or Renoir. Artistic and painterly, NOT a photo.",
    
    "watercolor": "Transform into a soft watercolor painting. Wet-on-wet technique, paint bleeds, artistic splatters, pastel colors on textured white paper. Dreamy and ethereal look.",

    # 3. МАТЕРИАЛЫ И 3D (Самые проблемные)
    "clay": "Transform into a CLAYMATION stop-motion scene. The subject must look like it is made of PLAY-DOH or PLASTICINE. Fingerprint textures on the clay, rounded soft edges, handmade look. Style of Aardman Animations (Wallace and Gromit). Miniature photography tilt-shift effect. NOT a drawing, NOT a photo.",
    
    "3d": "Transform into a Stylized 3D Character render (Disney/Pixar style). Smooth plastic skin, exaggerated subsurface scattering, soft studio lighting, cute proportions, big eyes. 3D CGI animation look. Octane render. NOT realistic, looks like a cartoon movie.",
    
    "lowpoly": "Transform into Low Poly 3D art. Composed entirely of visible geometric triangles and polygons. Sharp faceted edges, flat shading per face, minimalist abstract look. Video game PS1 aesthetic.",

    # 4. АТМОСФЕРНЫЕ
    "cyberpunk": "Transform into Cyberpunk style. Night time, neon blue and magenta lighting, rain-slicked streets, futuristic techwear, glowing holograms. High contrast, cinematic sci-fi atmosphere.",
    
    "steampunk": "Transform into Steampunk style. Materials: Brass, copper, leather, and wood. Add gears, cogs, steam pipes, and victorian clockwork mechanisms. Sepia and gold color palette. Retro-futuristic industrial look.",
    
    "noir": "Transform into 1940s Film Noir style. High contrast Black and White photography. Dramatic shadows (chiaroscuro), silhouette lighting, grain, moody detective movie atmosphere. Fog and mystery.",
    
    "pixel": "Transform into 16-bit Pixel Art. Retro video game sprite. Visible square pixels, limited color palette (32 colors), dithering. SNES or SEGA Genesis style graphics.",
    
    "ghibli": "Transform into Studio Ghibli background art. Hand-painted gouache style, lush green nature, fluffy cumulus clouds, peaceful atmosphere, vibrant but natural colors. Hayao Miyazaki aesthetic."
}


def stylize_image(image_bytes: bytes, style: str = "anime", model: str = "google/nano-banana-pro", retries: int = 3) -> BytesIO:
    """
    Стилизует изображение в выбранном художественном стиле.
    Использует Gemini или Segmind в зависимости от модели.
    """
    if model in ['google/nano-banana', 'google/nano-banana-pro']:
        logger.info(f"[Stylize] Switching from {model} to SeeDream (bytedance/seedream-4) for better quality")
        model = 'bytedance/seedream-4'
        
    # Для моделей Google пробуем сначала Gemini
    if model in ['google/nano-banana', 'google/nano-banana-pro']:
        try:
            from utils.gemini_service import is_gemini_available, stylize_image_gemini, GeminiError
            
            if is_gemini_available():
                logger.info(f"[Stylize] Trying Gemini for {model}")
                return stylize_image_gemini(image_bytes, style, model=model)
                
        except Exception as e:
            logger.warning(f"[Stylize] Gemini failed, using Segmind: {e}")
    
    # Segmind
    return stylize_image_segmind(image_bytes, style, model, retries)


def stylize_image_segmind(image_bytes: bytes, style: str, model: str, retries: int = 3) -> BytesIO:
    """
    Стилизует изображение через Segmind API.
    Автоматически сохраняет пропорции входного изображения.
    """
    from utils.segmind_service import SEGMIND_BASE_URL, is_segmind_available, MODEL_ENDPOINTS
    
    if not is_segmind_available():
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    # 1. Анализируем размеры исходного изображения
    try:
        pil_img = Image.open(BytesIO(image_bytes))
        orig_w, orig_h = pil_img.size
        orig_ratio = orig_w / orig_h
    except Exception as e:
        logger.warning(f"Could not determine image size: {e}")
        orig_w, orig_h = 1024, 1024
        orig_ratio = 1.0

    # Загружаем изображение на хостинг
    try:
        image_url = _upload_image(image_bytes)
    except Exception as e:
        raise ToolError(
            user_message="😔 Не удалось загрузить изображение.",
            technical_message=f"Image upload failed: {e}"
        )
    
    endpoint = MODEL_ENDPOINTS.get(model, 'nano-banana-pro')
    
    # Модели с поддержкой image_urls/image_input
    models_with_images = ['nano-banana', 'nano-banana-pro', 'seedream-4.5']
    if endpoint not in models_with_images and endpoint != 'flux-2-pro':
        endpoint = 'nano-banana-pro'
    
    url = f"{SEGMIND_BASE_URL}/{endpoint}"
    
    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["anime"])
    full_prompt = f"Completely transform this image: {style_prompt}. Transform the ENTIRE image including background."
    
    # --- ЛОГИКА СОХРАНЕНИЯ ПРОПОРЦИЙ ---
    
    # Список поддерживаемых форматов для Nano Banana / SeeDream
    # Словарь: "Название": Числовое_значение
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
    
    # Находим самый близкий формат
    closest_ratio_name = min(ratios.keys(), key=lambda k: abs(ratios[k] - orig_ratio))
    
    # Для Flux рассчитываем точные пиксели (кратные 32, около 1MPx)
    target_area = 1024 * 1024
    scale = (target_area / (orig_w * orig_h)) ** 0.5
    flux_w = int(round(orig_w * scale / 32) * 32)
    flux_h = int(round(orig_h * scale / 32) * 32)
    
    # Ограничиваем максимальный размер для Flux (на всякий случай)
    if flux_w > 1440: flux_w = 1440
    if flux_h > 1440: flux_h = 1440
    # -----------------------------------

    # Формируем payload
    if endpoint == 'seedream-4.5':
        payload = {
            "prompt": full_prompt,
            "image_input": [image_url],
            "aspect_ratio": closest_ratio_name, # Используем умный формат
            "max_images": 1
        }

    elif endpoint == 'flux-2-pro':
        payload = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "width": flux_w,    # Используем точные размеры
            "height": flux_h,   # Сохраняя пропорции оригинала
            "safety_tolerance": 3,
            "output_format": "png"
        }
    else:
        # nano-banana и nano-banana-pro
        payload = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "aspect_ratio": closest_ratio_name, # Используем умный формат
            "output_format": "png"
        }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[Stylize] Attempt {attempt + 1}/{retries} with {endpoint}. Ratio: {closest_ratio_name}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=180
            )
            
            result = _process_segmind_response(response, "Stylize")
            
            result.seek(0)
            compressed = _compress_image(result.read())
            return compressed
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Stylize] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось стилизовать изображение. Попробуйте позже.",
        technical_message=f"Stylize failed after {retries} attempts: {last_error}"
    )

# ============ ГЕНЕРАЦИЯ ПО РЕФЕРЕНСУ ============

def generate_with_reference(reference_bytes: bytes, prompt: str, model: str = "google/nano-banana-pro", retries: int = 3) -> BytesIO:
    """
    Генерирует новое изображение по промпту, копируя стиль референса.
    """
    
    # Для моделей Google пробуем сначала Gemini
    if model in ['google/nano-banana', 'google/nano-banana-pro']:
        try:
            from utils.gemini_service import is_gemini_available, generate_with_reference_gemini, GeminiError
            
            if is_gemini_available():
                logger.info(f"[Reference] Trying Gemini for {model}")
                return generate_with_reference_gemini(reference_bytes, prompt, model=model)
                
        except Exception as e:
            logger.warning(f"[Reference] Gemini failed, using Segmind: {e}")
    
    # Segmind
    return generate_with_reference_segmind(reference_bytes, prompt, model, retries)


def generate_with_reference_segmind(reference_bytes: bytes, prompt: str, model: str, retries: int = 3) -> BytesIO:
    """
    Генерирует изображение по референсу через Segmind.
    """
    from utils.segmind_service import SEGMIND_BASE_URL, is_segmind_available, MODEL_ENDPOINTS
    
    if not is_segmind_available():
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    # Загружаем референс на хостинг
    try:
        image_url = _upload_image(reference_bytes)
    except Exception as e:
        raise ToolError(
            user_message="😔 Не удалось загрузить изображение.",
            technical_message=f"Image upload failed: {e}"
        )
    
    endpoint = MODEL_ENDPOINTS.get(model, 'nano-banana-pro')
    
    if endpoint not in ['nano-banana', 'nano-banana-pro', 'seedream-4.5']:
        endpoint = 'nano-banana-pro'
    
    url = f"{SEGMIND_BASE_URL}/{endpoint}"
    
    full_prompt = (
        f"Create a completely NEW image showing: {prompt}. "
        f"Copy the EXACT artistic style from the reference image - "
        f"same color palette, same lighting style, same textures, "
        f"same artistic technique, same mood and atmosphere."
    )
    
    if endpoint == 'seedream-4.5':
        payload = {
            "prompt": full_prompt,
            "image_input": [image_url],
            "aspect_ratio": "1:1",
            "max_images": 1
        }
    else:
        payload = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "aspect_ratio": "1:1",
            "output_format": "png"
        }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[Reference] Attempt {attempt + 1}/{retries} with {endpoint}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=120
            )
            
            return _process_segmind_response(response, "Reference")
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Reference] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось сгенерировать изображение. Попробуйте позже.",
        technical_message=f"Reference generation failed: {last_error}"
    )

# ============ ТРАНСФОРМАЦИЯ ПО РЕФЕРЕНСУ ============

def transform_with_reference(reference_bytes: bytes, target_bytes: bytes, model: str = "google/nano-banana-pro", retries: int = 3) -> BytesIO:
    """
    Трансформирует целевое изображение в стиль референса.
    """
    
    # Для моделей Google пробуем сначала Gemini
    if model in ['google/nano-banana', 'google/nano-banana-pro']:
        try:
            from utils.gemini_service import is_gemini_available, transform_image_gemini, GeminiError
            
            if is_gemini_available():
                logger.info(f"[Transform] Trying Gemini for {model}")
                prompt = "Transform to match the style of the reference image."
                return transform_image_gemini(reference_bytes, target_bytes, prompt, model=model)
                
        except Exception as e:
            logger.warning(f"[Transform] Gemini failed, using Segmind: {e}")
    
    # Segmind
    return transform_with_reference_segmind(reference_bytes, target_bytes, model, retries)


def transform_with_reference_segmind(reference_bytes: bytes, target_bytes: bytes, model: str, retries: int = 3) -> BytesIO:
    """
    Трансформирует изображение через Segmind.
    """
    from utils.segmind_service import SEGMIND_BASE_URL, is_segmind_available, MODEL_ENDPOINTS
    
    if not is_segmind_available():
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    # Загружаем оба изображения на хостинг
    try:
        image_urls = _upload_images([reference_bytes, target_bytes])
    except Exception as e:
        raise ToolError(
            user_message="😔 Не удалось загрузить изображения.",
            technical_message=f"Image upload failed: {e}"
        )
    
    endpoint = MODEL_ENDPOINTS.get(model, 'nano-banana-pro')
    
    if endpoint not in ['nano-banana', 'nano-banana-pro', 'seedream-4.5']:
        endpoint = 'nano-banana-pro'
    
    url = f"{SEGMIND_BASE_URL}/{endpoint}"
    
    prompt = (
        "Transform the second image to match the EXACT artistic style of the first reference image. "
        "Copy the color palette, lighting, textures, and artistic technique from the reference. "
        "Keep the content of the second image but change its visual style completely."
    )
    
    if endpoint == 'seedream-4.5':
        payload = {
            "prompt": prompt,
            "image_input": image_urls,
            "aspect_ratio": "match_input_image",
            "max_images": 1
        }
    else:
        payload = {
            "prompt": prompt,
            "image_urls": image_urls,
            "aspect_ratio": "1:1",
            "output_format": "png"
        }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[Transform] Attempt {attempt + 1}/{retries} with {endpoint}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=120
            )
            
            result = _process_segmind_response(response, "Transform")
            
            # Сжимаем если слишком большое
            result.seek(0)
            compressed = _compress_image(result.read())
            return compressed
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Transform] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось трансформировать изображение. Попробуйте позже.",
        technical_message=f"Transform failed: {last_error}"
    )

# ============ БАННЕРЫ ============

def generate_banner(user_prompt: str, style_prompt: str, aspect_ratio: str = "1:1", retries: int = 3) -> BytesIO:
    """
    Генерирует маркетинговый баннер через Ideogram (лучше работает с текстом).
    """
    from utils.segmind_service import SEGMIND_BASE_URL, is_segmind_available
    
    if not is_segmind_available():
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    # Ideogram лучше для текста на баннерах
    url = f"{SEGMIND_BASE_URL}/ideogram-3"
    
    full_prompt = (
        f"Professional marketing banner advertisement. {user_prompt}. "
        f"{style_prompt}. "
        f"Clean professional layout, commercial quality, advertising design, "
        f"sharp text if any, high contrast, visually striking composition."
    )
    
    # Преобразуем aspect_ratio в формат ideogram
    ideogram_ratio = aspect_ratio.replace(":", "x")
    
    payload = {
        "prompt": full_prompt,
        "aspect_ratio": ideogram_ratio,
        "rendering_speed": "DEFAULT",
        "magic_prompt": "AUTO",
        "style_type": "DESIGN"
    }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[Banner] Attempt {attempt + 1}/{retries}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=120
            )
            
            return _process_segmind_response(response, "Banner")
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Banner] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось создать баннер. Попробуйте позже.",
        technical_message=f"Banner generation failed: {last_error}"
    )

def generate_with_reference_segmind(reference_bytes: bytes, prompt: str, model: str, retries: int = 3) -> BytesIO:
    """
    Генерирует изображение по референсу через Segmind.
    """
    from utils.segmind_service import SEGMIND_BASE_URL, is_segmind_available, MODEL_ENDPOINTS
    
    if not is_segmind_available():
        raise ToolError(
            user_message="😔 Сервис не настроен.",
            technical_message="Segmind API not configured"
        )
    
    # Загружаем референс на хостинг
    try:
        image_url = _upload_image(reference_bytes)
    except Exception as e:
        raise ToolError(
            user_message="😔 Не удалось загрузить изображение.",
            technical_message=f"Image upload failed: {e}"
        )
    
    endpoint = MODEL_ENDPOINTS.get(model, 'nano-banana-pro')
    
    models_with_images = ['nano-banana', 'nano-banana-pro', 'seedream-4.5']
    if endpoint not in models_with_images:
        endpoint = 'nano-banana-pro'
    
    url = f"{SEGMIND_BASE_URL}/{endpoint}"
    
    full_prompt = (
        f"Create a completely NEW image showing: {prompt}. "
        f"Copy the EXACT artistic style from the reference image - "
        f"same color palette, same lighting style, same textures, "
        f"same artistic technique, same mood and atmosphere."
    )
    
    if endpoint == 'seedream-4.5':
        payload = {
            "prompt": full_prompt,
            "image_input": [image_url],
            "aspect_ratio": "1:1",
            "max_images": 1
        }
    elif endpoint == 'flux-2-pro':
        payload = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "width": 1024,
            "height": 1024,
            "safety_tolerance": 3,
            "output_format": "png"
        }
    else:
        payload = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "aspect_ratio": "1:1",
            "output_format": "png"
        }
    
    last_error = None
    for attempt in range(retries):
        try:
            logger.info(f"[Reference] Attempt {attempt + 1}/{retries} with {endpoint}")
            
            response = requests.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=180
            )
            
            result = _process_segmind_response(response, "Reference")
            
            # Сжимаем если слишком большое
            result.seek(0)
            compressed = _compress_image(result.read())
            return compressed
            
        except ToolError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[Reference] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    
    raise ToolError(
        user_message="😔 Не удалось сгенерировать изображение. Попробуйте позже.",
        technical_message=f"Reference generation failed: {last_error}"
    )
from google import genai
from google.genai import types
from PIL import Image
import os
import base64
from io import BytesIO
from dotenv import load_dotenv
import logging
import time

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Инициализация клиента
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# Модели для генерации изображений
GEMINI_MODELS = {
    'google/nano-banana': 'gemini-2.5-flash-image',
    'google/nano-banana-pro': 'gemini-3-pro-image-preview'
}


class GeminiError(Exception):
    """Ошибка Gemini API"""
    pass


def is_gemini_available():
    """Проверяет, доступен ли Gemini API"""
    return client is not None


def _get_gemini_model(replicate_model: str) -> str:
    """Возвращает название Gemini модели"""
    return GEMINI_MODELS.get(replicate_model, GEMINI_MODELS['google/nano-banana'])


def _bytes_to_pil(image_bytes: bytes) -> Image.Image:
    """Конвертирует bytes в PIL Image"""
    return Image.open(BytesIO(image_bytes))


def _pil_to_base64(pil_image: Image.Image) -> str:
    """Конвертирует PIL Image в base64"""
    buffer = BytesIO()
    pil_image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def _extract_image_from_response(response) -> BytesIO:
    """Извлекает изображение из ответа Gemini"""
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image_data = part.inline_data.data
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            buffer = BytesIO(image_data)
            buffer.name = "result.png"
            return buffer
    raise GeminiError("No image in response")


def generate_image_gemini(prompt: str, aspect_ratio: str = "1:1", model: str = "google/nano-banana", retries: int = 2) -> BytesIO:
    """
    Генерирует изображение через Gemini API.
    """
    if not client:
        raise GeminiError("Gemini API not configured")
    
    gemini_model = _get_gemini_model(model)
    last_error = None
    
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=f"Generate an image: {prompt}. Aspect ratio: {aspect_ratio}.",
                config=types.GenerateContentConfig(
                    response_modalities=['image', 'text']
                )
            )
            
            return _extract_image_from_response(response)
                
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"[Gemini Generate] Attempt {attempt + 1}/{retries} failed: {e}")
            
            if "429" in error_str or "quota" in error_str.lower():
                time.sleep(5)
            elif "safety" in error_str.lower() or "blocked" in error_str.lower():
                raise GeminiError(f"Content blocked: {e}")
            elif attempt < retries - 1:
                time.sleep(2)
    
    raise GeminiError(f"Failed after {retries} attempts: {last_error}")


def edit_image_gemini(prompt: str, image_bytes: bytes, model: str = "google/nano-banana", retries: int = 2) -> BytesIO:
    """
    Редактирует изображение через Gemini API.
    """
    if not client:
        raise GeminiError("Gemini API not configured")
    
    gemini_model = _get_gemini_model(model)
    last_error = None
    
    for attempt in range(retries):
        try:
            pil_image = _bytes_to_pil(image_bytes)
            image_base64 = _pil_to_base64(pil_image)
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(text=f"Edit this image: {prompt}"),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/png",
                                    data=base64.b64decode(image_base64)
                                )
                            )
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=['image', 'text']
                )
            )
            
            return _extract_image_from_response(response)
                
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"[Gemini Edit] Attempt {attempt + 1}/{retries} failed: {e}")
            
            if "429" in error_str or "quota" in error_str.lower():
                time.sleep(5)
            elif "safety" in error_str.lower() or "blocked" in error_str.lower():
                raise GeminiError(f"Content blocked: {e}")
            elif attempt < retries - 1:
                time.sleep(2)
    
    raise GeminiError(f"Edit failed after {retries} attempts: {last_error}")


def transform_image_gemini(reference_bytes: bytes, target_bytes: bytes, prompt: str, model: str = "google/nano-banana", retries: int = 2) -> BytesIO:
    """
    Трансформирует изображение в стиль референса через Gemini API.
    """
    if not client:
        raise GeminiError("Gemini API not configured")
    
    gemini_model = _get_gemini_model(model)
    last_error = None
    
    for attempt in range(retries):
        try:
            ref_image = _bytes_to_pil(reference_bytes)
            ref_base64 = _pil_to_base64(ref_image)
            
            target_image = _bytes_to_pil(target_bytes)
            target_base64 = _pil_to_base64(target_image)
            
            transform_prompt = f"""Transform the second image to match the artistic style of the first reference image.
Copy the color palette, lighting, textures, and artistic technique from the reference.
Keep the content of the second image but change its visual style.
{prompt}"""
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(text="Style reference image:"),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/png",
                                    data=base64.b64decode(ref_base64)
                                )
                            ),
                            types.Part(text="Image to transform:"),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/png",
                                    data=base64.b64decode(target_base64)
                                )
                            ),
                            types.Part(text=transform_prompt)
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=['image', 'text']
                )
            )
            
            return _extract_image_from_response(response)
                
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"[Gemini Transform] Attempt {attempt + 1}/{retries} failed: {e}")
            
            if "429" in error_str or "quota" in error_str.lower():
                time.sleep(5)
            elif "safety" in error_str.lower() or "blocked" in error_str.lower():
                raise GeminiError(f"Content blocked: {e}")
            elif attempt < retries - 1:
                time.sleep(2)
    
    raise GeminiError(f"Transform failed after {retries} attempts: {last_error}")


def generate_with_reference_gemini(reference_bytes: bytes, prompt: str, model: str = "google/nano-banana", retries: int = 2) -> BytesIO:
    """
    Генерирует изображение по референсу через Gemini API.
    """
    if not client:
        raise GeminiError("Gemini API not configured")
    
    gemini_model = _get_gemini_model(model)
    last_error = None
    
    for attempt in range(retries):
        try:
            ref_image = _bytes_to_pil(reference_bytes)
            ref_base64 = _pil_to_base64(ref_image)
            
            reference_prompt = f"""Use this image as a STYLE REFERENCE.
Create a completely NEW image showing: {prompt}
Copy the artistic style, color palette, lighting, and technique from the reference.
Do NOT copy the content, only the visual style."""
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(text="Style reference:"),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/png",
                                    data=base64.b64decode(ref_base64)
                                )
                            ),
                            types.Part(text=reference_prompt)
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=['image', 'text']
                )
            )
            
            return _extract_image_from_response(response)
                
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"[Gemini Reference] Attempt {attempt + 1}/{retries} failed: {e}")
            
            if "429" in error_str or "quota" in error_str.lower():
                time.sleep(5)
            elif "safety" in error_str.lower() or "blocked" in error_str.lower():
                raise GeminiError(f"Content blocked: {e}")
            elif attempt < retries - 1:
                time.sleep(2)
    
    raise GeminiError(f"Reference generation failed after {retries} attempts: {last_error}")


def stylize_image_gemini(image_bytes: bytes, style: str, model: str = "google/nano-banana", retries: int = 2) -> BytesIO:
    """
    Стилизует изображение через Gemini API.
    """
    if not client:
        raise GeminiError("Gemini API not configured")
    
    style_prompts = {
        "anime": "Transform into anime style. Cel shaded, vibrant colors, big expressive eyes, japanese animation aesthetic.",
        "cartoon": "Transform into 3D Pixar cartoon style. Disney Pixar character, smooth plastic look, colorful cartoon.",
        "sketch": "Transform into pencil sketch. Black and white pencil drawing, detailed graphite lines.",
        "painting": "Transform into oil painting. Classical oil painting style, visible brush strokes, impressionist art.",
        "cyberpunk": "Transform into cyberpunk style. Neon purple and blue glow, futuristic sci-fi aesthetic.",
        "watercolor": "Transform into watercolor painting. Soft watercolor wash, wet paint effect, pastel colors.",
        "pixel": "Transform into pixel art. 16-bit retro game style, pixelated graphics, limited color palette.",
        "comic": "Transform into comic book style. Bold black ink outlines, halftone dots, vibrant pop art colors.",
        "3d": "COMPLETELY TRANSFORM into hyper-realistic 3D CGI render. Make it look like Pixar or Disney 3D animation. Smooth plastic skin, perfect 3D lighting, ray tracing, octane render quality, cinema 4D, Unreal Engine 5 quality. The person should look like a 3D animated character, NOT a real photo.",
        "ghibli": "Transform into Studio Ghibli style. Hayao Miyazaki art, soft dreamy colors, magical atmosphere."
    }
    
    style_prompt = style_prompts.get(style, style_prompts["anime"])
    gemini_model = _get_gemini_model(model)
    last_error = None
    
    for attempt in range(retries):
        try:
            pil_image = _bytes_to_pil(image_bytes)
            image_base64 = _pil_to_base64(pil_image)
            
            full_prompt = f"Completely transform this image: {style_prompt}. Transform the ENTIRE image including background."
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(text=full_prompt),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/png",
                                    data=base64.b64decode(image_base64)
                                )
                            )
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=['image', 'text']
                )
            )
            
            return _extract_image_from_response(response)
                
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"[Gemini Stylize] Attempt {attempt + 1}/{retries} failed: {e}")
            
            if "429" in error_str or "quota" in error_str.lower():
                time.sleep(5)
            elif "safety" in error_str.lower() or "blocked" in error_str.lower():
                raise GeminiError(f"Content blocked: {e}")
            elif attempt < retries - 1:
                time.sleep(2)
    
    raise GeminiError(f"Stylize failed after {retries} attempts: {last_error}")
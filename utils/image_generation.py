import logging
from io import BytesIO

logger = logging.getLogger(__name__)

MODEL_NAMES = {
    'google/nano-banana': 'Nano Banana',
    'google/nano-banana-pro': 'Nano Banana Pro',
    'bytedance/seedream-4': 'SeeDream 4.5',
    'ideogram-ai/ideogram-v2': 'Ideogram V3',
    'recraft-ai/recraft-v3': 'Recraft V3',
    'black-forest-labs/flux-1.1-pro': 'Flux 2 Pro',
    'stability-ai/stable-diffusion-3.5-large': 'SD 3.5 Large'
}

# Стоимость генерации для каждой модели
MODEL_COSTS = {
    'google/nano-banana': 1,
    'google/nano-banana-pro': 5,
    'bytedance/seedream-4': 1,
    'ideogram-ai/ideogram-v2': 1,
    'recraft-ai/recraft-v3': 1,
    'black-forest-labs/flux-1.1-pro': 2,
    'stability-ai/stable-diffusion-3.5-large': 1
}


def get_model_display_name(model: str) -> str:
    """Возвращает отображаемое имя модели"""
    return MODEL_NAMES.get(model, model)


def get_model_cost(model: str) -> int:
    """Возвращает стоимость генерации для модели"""
    return MODEL_COSTS.get(model, 1)


def generate_image(model: str, prompt: str, aspect_ratio: str) -> BytesIO:
    """
    Генерирует изображение через Segmind API.
    Сначала пробует Gemini для моделей Google, затем Segmind.
    """
    
    # Для моделей Google пробуем сначала Gemini (если настроен)
    # if model in ['google/nano-banana', 'google/nano-banana-pro']:
    #     try:
    #         from utils.gemini_service import is_gemini_available, generate_image_gemini, GeminiError
            
    #         if is_gemini_available():
    #             logger.info(f"[Generate] Trying Gemini for {model}")
    #             return generate_image_gemini(prompt, aspect_ratio, model=model)
                
    #     except Exception as e:
    #         logger.warning(f"[Generate] Gemini failed, falling back to Segmind: {e}")
    
    # Основной путь — Segmind
    from utils.segmind_service import generate_image_segmind, SegmindError, is_segmind_available
    
    if not is_segmind_available():
        raise Exception("Сервис генерации не настроен. Проверьте SEGMIND_API_TOKEN.")
    
    logger.info(f"[Generate] Using Segmind for {model}")
    return generate_image_segmind(prompt, aspect_ratio, model)


def edit_image(model: str, prompt: str, image_bytes: bytes) -> BytesIO:
    """
    Редактирует изображение.
    Сначала пробует Gemini для моделей Google, затем Segmind.
    """
    
    # Для моделей Google пробуем сначала Gemini
    # if model in ['google/nano-banana', 'google/nano-banana-pro']:
    #     try:
    #         from utils.gemini_service import is_gemini_available, edit_image_gemini, GeminiError
            
    #         if is_gemini_available():
    #             logger.info(f"[Edit] Trying Gemini for {model}")
    #             return edit_image_gemini(prompt, image_bytes, model=model)
                
    #     except Exception as e:
    #         logger.warning(f"[Edit] Gemini failed, falling back to Segmind: {e}")
    
    # Основной путь — Segmind
    from utils.segmind_service import edit_image_segmind, SegmindError, is_segmind_available
    
    if not is_segmind_available():
        raise Exception("Сервис редактирования не настроен. Проверьте SEGMIND_API_TOKEN.")
    
    logger.info(f"[Edit] Using Segmind for {model}")
    return edit_image_segmind(prompt, image_bytes, model)
import os
import requests
from dotenv import load_dotenv

load_dotenv()

REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')

def enhance_prompt(user_prompt: str, style: str = "general") -> str:
    """
    Улучшает промпт пользователя с помощью AI.
    
    Args:
        user_prompt: Оригинальный промпт пользователя
        style: Стиль улучшения (general, photo, art, marketing)
    
    Returns:
        Улучшенный промпт на английском
    """
    
    style_instructions = {
        "general": "Make it detailed and visually appealing.",
        "photo": "Make it photorealistic with proper lighting and composition.",
        "art": "Make it artistic with creative style and aesthetics.",
        "marketing": "Make it professional, eye-catching, suitable for advertising.",
        "banner": "Make it suitable for marketing banner with bold visuals and clean composition."
    }
    
    style_hint = style_instructions.get(style, style_instructions["general"])
    
    system_prompt = f"""You are an expert prompt engineer for AI image generation.
Your task is to enhance user prompts to create better images.

Rules:
1. Translate to English if needed
2. Add descriptive details (lighting, composition, style, mood)
3. Add quality modifiers (8k, detailed, professional, etc.)
4. Keep the original intent
5. Make it 1-3 sentences max
6. {style_hint}

Return ONLY the enhanced prompt, nothing else."""

    try:
        import replicate
        
        # Используем быструю модель для улучшения промптов
        output = replicate.run(
            "meta/meta-llama-3-8b-instruct",
            input={
                "prompt": f"Enhance this image prompt: {user_prompt}",
                "system_prompt": system_prompt,
                "max_tokens": 200,
                "temperature": 0.7
            }
        )
        
        # Собираем ответ
        enhanced = "".join(output).strip()
        
        # Убираем возможные кавычки и лишний текст
        enhanced = enhanced.strip('"\'')
        
        # Если ответ слишком короткий или пустой, возвращаем оригинал
        if len(enhanced) < 10:
            return user_prompt
        
        return enhanced
        
    except Exception as e:
        print(f"Ошибка улучшения промпта: {e}")
        # В случае ошибки возвращаем оригинальный промпт
        return user_prompt


def quick_enhance(user_prompt: str) -> str:
    """
    Быстрое улучшение промпта без AI (добавление модификаторов).
    Используется как fallback или для экономии.
    """
    
    quality_modifiers = [
        "highly detailed",
        "professional quality",
        "8k resolution",
        "sharp focus"
    ]
    
    # Проверяем, есть ли уже модификаторы качества
    prompt_lower = user_prompt.lower()
    has_quality = any(mod in prompt_lower for mod in ["8k", "4k", "detailed", "quality", "professional"])
    
    if has_quality:
        return user_prompt
    
    # Добавляем модификаторы
    enhanced = f"{user_prompt}, {', '.join(quality_modifiers)}"
    
    return enhanced
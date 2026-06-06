from telebot import types

# Информация о моделях с ценами
MODELS_INFO = [
    {
        'id': 'google/nano-banana',
        'name': 'Nano Banana',
        'cost': 1,
        'description': '🟢 <b>Базовая модель</b>\n\nОт Google DeepMind. Быстрая генерация, хорошее качество для большинства задач.\n\n⚡ Скорость: быстрая\n💎 Стоимость: 1 генерация'
    },
    {
        'id': 'google/nano-banana-pro',
        'name': 'Nano Banana Pro',
        'cost': 5,
        'description': '🟡 <b>Продвинутая модель</b>\n\nЛучшее понимание промптов, высокая детализация.\n\n⚡ Скорость: средняя\n💎 Стоимость: 5 генераций'
    },
    {
        'id': 'bytedance/seedream-4',
        'name': 'SeeDream 4.5',
        'cost': 1,
        'description': '🔵 <b>Детализация</b>\n\nОт ByteDance. Отличная детализация, реалистичные изображения, хорошая работа с людьми.\n\n⚡ Скорость: средняя\n💎 Стоимость: 1 генерация'
    },
    {
        'id': 'ideogram-ai/ideogram-v2',
        'name': 'Ideogram V3',
        'cost': 1,
        'description': '📝 <b>Лучший для текста</b>\n\nИдеален для баннеров, постеров, логотипов. Отлично рендерит текст на изображениях.\n\n⚡ Скорость: средняя\n💎 Стоимость: 1 генерация'
    },
    {
        'id': 'recraft-ai/recraft-v3',
        'name': 'Recraft V3',
        'cost': 1,
        'description': '🎨 <b>Векторная графика</b>\n\nИллюстрации, иконки, инфографика. Чистые линии и профессиональный дизайн.\n\n⚡ Скорость: средняя\n💎 Стоимость: 1 генерация'
    },
    {
        'id': 'black-forest-labs/flux-1.1-pro',
        'name': 'Flux 2 Pro',
        'cost': 2,
        'description': '⭐ <b>Премиум качество</b>\n\nВысочайшее качество и детализация. Продуктовые фото, реклама, профессиональный арт.\n\n⚡ Скорость: медленная\n💎 Стоимость: 2 генерации'
    }
    # {
    #     'id': 'stability-ai/stable-diffusion-3.5-large',
    #     'name': 'SD 3.5 Large',
    #     'cost': 1,
    #     'description': '🚀 <b>Универсальная</b>\n\nБыстрая и универсальная модель от Stability AI. Подходит для любого контента.\n\n⚡ Скорость: быстрая\n💎 Стоимость: 1 генерация'
    # }
]


def get_models_info():
    """Возвращает информацию о всех моделях"""
    return MODELS_INFO


def get_model_cost(model_id: str) -> int:
    """Возвращает стоимость генерации для модели"""
    for model in MODELS_INFO:
        if model['id'] == model_id:
            return model['cost']
    return 1  # По умолчанию 1


def get_model_selection_keyboard(current_page=0, selected_model_id=None):
    """Клавиатура для выбора модели с пагинацией"""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    
    models = get_models_info()
    current_model = models[current_page]
    
    # Формируем текст кнопки с ценой
    cost_text = f"({current_model['cost']} ген.)" if current_model['cost'] > 1 else "(1 ген.)"
    
    if current_model['id'] == selected_model_id:
        button_text = f"✅ {current_model['name']} {cost_text}"
    else:
        button_text = f"Выбрать {current_model['name']} {cost_text}"
    
    keyboard.add(
        types.InlineKeyboardButton(
            button_text, 
            callback_data=f"select_model_{current_model['id']}"
        )
    )
    
    # Навигация
    nav_buttons = []
    
    if current_page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"model_page_{current_page - 1}"))
    
    nav_buttons.append(types.InlineKeyboardButton(f"{current_page + 1}/{len(models)}", callback_data="model_page_info"))
    
    if current_page < len(models) - 1:
        nav_buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"model_page_{current_page + 1}"))
    
    keyboard.row(*nav_buttons)
    
    # Кнопка назад
    keyboard.add(types.InlineKeyboardButton("◀️ Главное меню", callback_data="back_to_main"))
    
    return keyboard, current_model
from telebot import types

def get_main_menu_keyboard():
    """Inline клавиатура главного меню"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton('🎨 Создать', callback_data='menu_create'),
        types.InlineKeyboardButton('✏️ Редактировать', callback_data='menu_edit')
    )
    keyboard.add(
        types.InlineKeyboardButton('🛠 Инструменты', callback_data='menu_tools'),
        types.InlineKeyboardButton('🤖 Модель', callback_data='menu_model')
    )
    keyboard.add(
        types.InlineKeyboardButton('💰 Купить', callback_data='menu_buy'),
        types.InlineKeyboardButton('ℹ️ Информация', callback_data='menu_info')
    )
    return keyboard

def get_tools_keyboard():
    """Клавиатура инструментов"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('🔮 Удалить фон', callback_data='tool_remove_bg'),
        types.InlineKeyboardButton('📈 Апскейл (улучшить качество)', callback_data='tool_upscale'),
        types.InlineKeyboardButton('🎨 Стилизация фото', callback_data='tool_stylize'),
        types.InlineKeyboardButton('🖼 Генерация по референсу', callback_data='tool_reference'),
        types.InlineKeyboardButton('📢 Маркетинговые баннеры', callback_data='tool_banners'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard

def get_aspect_ratio_keyboard():
    """Клавиатура выбора формата изображения"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(types.InlineKeyboardButton('📦 КВАДРАТ', callback_data='category_ignore'))
    keyboard.add(
        types.InlineKeyboardButton('1:1', callback_data='aspect_1:1')
    )
    
    keyboard.add(types.InlineKeyboardButton('📱 ПОРТРЕТ', callback_data='category_ignore'))
    keyboard.add(
        types.InlineKeyboardButton('2:3', callback_data='aspect_2:3'),
        types.InlineKeyboardButton('3:4', callback_data='aspect_3:4')
    )
    keyboard.add(
        types.InlineKeyboardButton('4:5', callback_data='aspect_4:5'),
        types.InlineKeyboardButton('9:16', callback_data='aspect_9:16')
    )
    
    keyboard.add(types.InlineKeyboardButton('🖼 АЛЬБОМ', callback_data='category_ignore'))
    keyboard.add(
        types.InlineKeyboardButton('3:2', callback_data='aspect_3:2'),
        types.InlineKeyboardButton('4:3', callback_data='aspect_4:3')
    )
    keyboard.add(
        types.InlineKeyboardButton('5:4', callback_data='aspect_5:4'),
        types.InlineKeyboardButton('16:9', callback_data='aspect_16:9')
    )
    keyboard.add(types.InlineKeyboardButton('21:9', callback_data='aspect_21:9'))
    
    keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_create'))
    
    return keyboard

def get_create_image_keyboard(current_aspect='1:1', enhance_enabled=True, model_cost=1):
    """Клавиатура в режиме создания изображения"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(
        types.InlineKeyboardButton(f'📐 Формат: {current_aspect}', callback_data='change_aspect_ratio')
    )
    keyboard.add(
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard

def get_edit_image_keyboard():
    """Клавиатура в режиме редактирования изображения"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='cancel_edit')
    )
    return keyboard

def get_after_edit_keyboard():
    """Клавиатура после успешного редактирования"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('✏️ Продолжить редактирование', callback_data='continue_edit_same')
    )
    keyboard.add(
        types.InlineKeyboardButton('📷 Загрузить другое изображение', callback_data='continue_edit_new')
    )
    keyboard.add(
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='cancel_edit')
    )
    return keyboard

def get_tool_back_keyboard():
    """Клавиатура возврата из инструмента"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('🛠 К инструментам', callback_data='menu_tools'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard

def get_stylize_keyboard():
    """Клавиатура выбора стиля"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Группа 1: Рисованные / Анимация
    keyboard.add(
        types.InlineKeyboardButton('🎌 Аниме', callback_data='style_anime'),
        types.InlineKeyboardButton('📺 2D Мульт', callback_data='style_cartoon') # Изменили название для ясности
    )
    
    # Группа 2: Художественные техники
    keyboard.add(
        types.InlineKeyboardButton('✏️ Скетч', callback_data='style_sketch'),
        types.InlineKeyboardButton('🖼 Живопись', callback_data='style_painting')
    )
    
    # Группа 3: Атмосферные
    keyboard.add(
        types.InlineKeyboardButton('🌆 Киберпанк', callback_data='style_cyberpunk'),
        types.InlineKeyboardButton('⚙️ Стимпанк', callback_data='style_steampunk') # Новый
    )
    
    # Группа 4: Необычные техники
    keyboard.add(
        types.InlineKeyboardButton('🎨 Акварель', callback_data='style_watercolor'),
        types.InlineKeyboardButton('🧱 Пластилин', callback_data='style_clay') # Новый
    )
    
    # Группа 5: Графика и Ретро
    keyboard.add(
        types.InlineKeyboardButton('👾 Пиксель-арт', callback_data='style_pixel'),
        types.InlineKeyboardButton('💥 Комикс', callback_data='style_comic')
    )

    # Группа 6: 3D и Геометрия
    keyboard.add(
        types.InlineKeyboardButton('🎮 3D Реализм', callback_data='style_3d'), # Уточнили название
        types.InlineKeyboardButton('🔷 Low Poly', callback_data='style_lowpoly') # Новый
    )
    
    # Группа 7: Кино и Атмосфера
    keyboard.add(
        types.InlineKeyboardButton('🕵️ Нуар', callback_data='style_noir'), # Новый
        types.InlineKeyboardButton('🏯 Студия Гибли', callback_data='style_ghibli')
    )
    
    # Навигация
    keyboard.add(
        types.InlineKeyboardButton('◀️ Назад', callback_data='menu_tools')
    )
    
    return keyboard

def remove_reply_keyboard():
    """Удаляет reply клавиатуру"""
    return types.ReplyKeyboardRemove()

def get_banner_format_keyboard():
    """Клавиатура выбора формата баннера"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('📱 Stories 9:16', callback_data='banner_9:16'),
        types.InlineKeyboardButton('📐 Пост 1:1', callback_data='banner_1:1'),
        types.InlineKeyboardButton('🖼 Facebook 16:9', callback_data='banner_16:9'),
        types.InlineKeyboardButton('📺 YouTube 16:9', callback_data='banner_16:9_yt'),
        types.InlineKeyboardButton('🛒 Товар 1:1', callback_data='banner_1:1_product'),
        types.InlineKeyboardButton('🏷 Широкий 21:9', callback_data='banner_21:9'),
        types.InlineKeyboardButton('◀️ Назад', callback_data='menu_tools')
    )
    return keyboard


def get_banner_style_keyboard():
    """Клавиатура выбора стиля баннера"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton('✨ Минимализм', callback_data='bstyle_minimal'),
        types.InlineKeyboardButton('🎨 Яркий', callback_data='bstyle_vibrant')
    )
    keyboard.add(
        types.InlineKeyboardButton('👔 Премиум', callback_data='bstyle_premium'),
        types.InlineKeyboardButton('🎉 Праздник', callback_data='bstyle_festive')
    )
    keyboard.add(
        types.InlineKeyboardButton('🌿 Эко', callback_data='bstyle_eco'),
        types.InlineKeyboardButton('⚡ Тех', callback_data='bstyle_tech')
    )
    keyboard.add(
        types.InlineKeyboardButton('◀️ Назад', callback_data='tool_banners')
    )
    return keyboard

def get_after_generation_keyboard(current_model, aspect_ratio, enhance_enabled=True):
    """Клавиатура после генерации с предложением другой модели"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Определяем альтернативную модель
    alternative_models = {
        'google/nano-banana': ('google/nano-banana-pro', '🚀 Попробовать Nano Banana Pro'),
        'google/nano-banana-pro': ('ideogram-ai/ideogram-v2', '📝 Попробовать Ideogram (лучше текст)'),
        'bytedance/seedream-4': ('black-forest-labs/flux-1.1-pro', '⭐ Попробовать Flux Pro'),
        'ideogram-ai/ideogram-v2': ('google/nano-banana-pro', '🚀 Попробовать Nano Banana Pro'),
        'recraft-ai/recraft-v3': ('ideogram-ai/ideogram-v2', '📝 Попробовать Ideogram'),
        'black-forest-labs/flux-1.1-pro': ('google/nano-banana-pro', '🚀 Попробовать Nano Banana Pro'),
        'stability-ai/stable-diffusion-3.5-large': ('black-forest-labs/flux-1.1-pro', '⭐ Попробовать Flux Pro')
    }
    
    alt_model, alt_text = alternative_models.get(
        current_model, 
        ('google/nano-banana-pro', '🚀 Попробовать другую модель')
    )
    
    keyboard.add(
        types.InlineKeyboardButton(alt_text, callback_data=f'try_model_{alt_model}')
    )
    
    # Кнопка улучшения промпта
    # enhance_status = "✅" if enhance_enabled else "❌"
    # keyboard.add(
    #     types.InlineKeyboardButton(
    #         f'✨ Улучшение промпта: {enhance_status}', 
    #         callback_data='toggle_enhance'
    #     )
    # )
    
    keyboard.add(
        types.InlineKeyboardButton(f'📐 Формат: {aspect_ratio}', callback_data='change_aspect_ratio')
    )
    keyboard.add(
        types.InlineKeyboardButton('🤖 Все модели', callback_data='menu_model')
    )
    keyboard.add(
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    
    return keyboard
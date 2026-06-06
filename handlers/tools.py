from keyboards.reply import (
    get_main_menu_keyboard, get_tools_keyboard, 
    get_tool_back_keyboard, get_stylize_keyboard,
    get_banner_format_keyboard, get_banner_style_keyboard
)
from utils.db_utils import get_balance, get_user_model
from utils.image_generation import get_model_display_name, get_model_cost
from utils.task_queue import create_task
from telebot import types
from utils.constants import BOT_SIGNATURE

# Состояния инструментов (в памяти для быстрого доступа)
tool_states = {}
tool_images = {}
banner_data = {}
reference_images = {}
reference_target_images = {}

# Поддерживаемые форматы
SUPPORTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp']
SUPPORTED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']

# Названия стилей
STYLE_NAMES = {
    'anime': '🎌 Аниме',
    'cartoon': '🎬 Мультфильм',
    'sketch': '✏️ Скетч',
    'painting': '🖼 Живопись',
    'cyberpunk': '🌆 Киберпанк',
    'watercolor': '🎨 Акварель',
    'pixel': '👾 Пиксель-арт',
    'comic': '💥 Комикс',
    '3d': '🎮 3D рендер',
    'ghibli': '🏯 Студия Гибли'
}


def is_image_document(document):
    """Проверяет, является ли документ изображением"""
    if document.mime_type and document.mime_type in SUPPORTED_MIME_TYPES:
        return True
    if document.file_name:
        ext = document.file_name.lower().split('.')[-1]
        if ext in SUPPORTED_EXTENSIONS:
            return True
    return False


def cleanup_user_tool_state(user_id):
    """Очищает все состояния инструментов для пользователя"""
    if user_id in tool_states:
        del tool_states[user_id]
    if user_id in tool_images:
        del tool_images[user_id]
    if user_id in banner_data:
        del banner_data[user_id]
    if user_id in reference_images:
        del reference_images[user_id]
    if user_id in reference_target_images:
        del reference_target_images[user_id]


def register_handlers(bot):
    
    # ============ УДАЛЕНИЕ ФОНА ============
    
    @bot.callback_query_handler(func=lambda call: call.data == 'tool_remove_bg')
    def tool_remove_bg_callback(call):
        """Инструмент удаления фона"""
        user_id = call.from_user.id
        
        bot.edit_message_text(
            (
                "🔮 <b>Удаление фона</b>\n\n"
                "Отправьте изображение, с которого нужно удалить фон.\n\n"
                "<i>Лучше всего работает с фотографиями людей, товаров и объектов на однородном фоне.</i>\n\n"
                "💎 Стоимость: 1 генерация"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_tool_back_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_remove_bg'
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(
        content_types=['photo'],
        func=lambda message: tool_states.get(message.from_user.id) == 'waiting_remove_bg'
    )
    def handle_remove_bg_photo(message):
        """Обработка фото для удаления фона"""
        process_remove_bg_task(bot, message, message.photo[-1].file_id)
    
    @bot.message_handler(
        content_types=['document'],
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_remove_bg'
            and message.document
            and is_image_document(message.document)
        )
    )
    def handle_remove_bg_document(message):
        """Обработка документа для удаления фона"""
        process_remove_bg_task(bot, message, message.document.file_id)
    
    # ============ АПСКЕЙЛ ============
    
    @bot.callback_query_handler(func=lambda call: call.data == 'tool_upscale')
    def tool_upscale_callback(call):
        """Инструмент апскейла"""
        user_id = call.from_user.id
        
        bot.edit_message_text(
            (
                "📈 <b>Апскейл изображения</b>\n\n"
                "Отправьте изображение для увеличения разрешения и улучшения качества.\n\n"
                "<i>Изображение будет увеличено в 2-4 раза с сохранением деталей.</i>\n\n"
                "💎 Стоимость: 1 генерация"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_tool_back_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_upscale'
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(
        content_types=['photo'],
        func=lambda message: tool_states.get(message.from_user.id) == 'waiting_upscale'
    )
    def handle_upscale_photo(message):
        """Обработка фото для апскейла"""
        process_upscale_task(bot, message, message.photo[-1].file_id)
    
    @bot.message_handler(
        content_types=['document'],
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_upscale'
            and message.document
            and is_image_document(message.document)
        )
    )
    def handle_upscale_document(message):
        """Обработка документа для апскейла"""
        process_upscale_task(bot, message, message.document.file_id)
    
    # ============ СТИЛИЗАЦИЯ ============
    
    @bot.callback_query_handler(func=lambda call: call.data == 'tool_stylize')
    def tool_stylize_callback(call):
        """Инструмент стилизации"""
        user_id = call.from_user.id
        model, _ = get_user_model(user_id)
        cost = get_model_cost(model)
        model_display = get_model_display_name(model)
        
        bot.edit_message_text(
            (
                f"🎨 <b>Стилизация фото</b>\n\n"
                f"Отправьте фотографию, которую хотите превратить в арт.\n\n"
                f"🤖 Модель: {model_display}\n"
                f"💎 Стоимость: {cost} генераций"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_tool_back_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_stylize_image'
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(
        content_types=['photo'],
        func=lambda message: tool_states.get(message.from_user.id) == 'waiting_stylize_image'
    )
    def handle_stylize_photo(message):
        """Получение фото для стилизации"""
        user_id = message.from_user.id
        tool_images[user_id] = message.photo[-1].file_id
        
        bot.send_message(
            message.chat.id,
            (
                "✅ <b>Фото получено!</b>\n\n"
                "Выберите стиль:"
            ),
            reply_markup=get_stylize_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_stylize_style'
    
    @bot.message_handler(
        content_types=['document'],
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_stylize_image'
            and message.document
            and is_image_document(message.document)
        )
    )
    def handle_stylize_document(message):
        """Получение документа для стилизации"""
        user_id = message.from_user.id
        tool_images[user_id] = message.document.file_id
        
        bot.send_message(
            message.chat.id,
            (
                "✅ <b>Изображение получено!</b>\n\n"
                "Выберите стиль:"
            ),
            reply_markup=get_stylize_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_stylize_style'
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('style_'))
    def handle_style_selection(call):
        """Обработка выбора стиля"""
        user_id = call.from_user.id
        
        if user_id not in tool_images:
            bot.answer_callback_query(call.id, "❌ Сначала отправьте изображение")
            return
        
        style = call.data.replace('style_', '')
        style_name = STYLE_NAMES.get(style, style)
        
        bot.answer_callback_query(call.id, f"Выбран стиль: {style_name}")
        
        process_stylize_task(bot, call.message, user_id, tool_images[user_id], style, style_name)

    @bot.callback_query_handler(func=lambda call: call.data == 'stylize_another_style')
    def stylize_another_style_callback(call):
        """Выбрать другой стиль для того же фото"""
        user_id = call.from_user.id
        
        if user_id not in tool_images:
            bot.answer_callback_query(call.id, "❌ Фото не найдено, загрузите новое")
            tool_stylize_callback(call)
            return
        
        bot.edit_message_text(
            (
                "🎨 <b>Выберите другой стиль:</b>\n\n"
                "<i>Используем то же изображение</i>"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_stylize_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_stylize_style'
        bot.answer_callback_query(call.id)

    # ============ ГЕНЕРАЦИЯ ПО РЕФЕРЕНСУ ============
    
    @bot.callback_query_handler(func=lambda call: call.data == 'tool_reference')
    def tool_reference_callback(call):
        """Инструмент генерации по референсу"""
        user_id = call.from_user.id
        model, _ = get_user_model(user_id)
        cost = get_model_cost(model)
        model_display = get_model_display_name(model)
        
        bot.edit_message_text(
            (
                f"🖼 <b>Генерация по референсу</b>\n\n"
                f"Загрузите изображение-референс, стиль которого хотите использовать.\n\n"
                f"<i>Например: картина, иллюстрация, фото в определённом стиле</i>\n\n"
                f"🤖 Модель: {model_display}\n"
                f"💎 Стоимость: {cost} генераций"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_tool_back_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_reference_image'
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(
        content_types=['photo'],
        func=lambda message: tool_states.get(message.from_user.id) == 'waiting_reference_image'
    )
    def handle_reference_photo(message):
        """Получение референса"""
        user_id = message.from_user.id
        reference_images[user_id] = message.photo[-1].file_id
        
        bot.send_message(
            message.chat.id,
            (
                "✅ <b>Референс получен!</b>\n\n"
                "Теперь выберите, что делать:\n\n"
                "📝 <b>Отправьте текст</b> — опишите, что нарисовать в этом стиле\n"
                "📷 <b>Отправьте фото</b> — трансформируем его в стиль референса"
            ),
            reply_markup=get_reference_choice_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_reference_choice'
    
    @bot.message_handler(
        content_types=['document'],
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_reference_image'
            and message.document
            and is_image_document(message.document)
        )
    )
    def handle_reference_document(message):
        """Получение референса как документа"""
        user_id = message.from_user.id
        reference_images[user_id] = message.document.file_id
        
        bot.send_message(
            message.chat.id,
            (
                "✅ <b>Референс получен!</b>\n\n"
                "Теперь выберите, что делать:\n\n"
                "📝 <b>Отправьте текст</b> — опишите, что нарисовать в этом стиле\n"
                "📷 <b>Отправьте фото</b> — трансформируем его в стиль референса"
            ),
            reply_markup=get_reference_choice_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_reference_choice'
    
    @bot.message_handler(
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_reference_choice'
            and message.text
            and not message.text.startswith('/')
        )
    )
    def handle_reference_text_choice(message):
        """Пользователь отправил текст — генерируем по описанию"""
        user_id = message.from_user.id
        
        if user_id not in reference_images:
            bot.send_message(
                message.chat.id,
                '❌ Референс не найден. Загрузите изображение заново.',
                reply_markup=get_tool_back_keyboard(),
                parse_mode='HTML'
            )
            tool_states[user_id] = 'waiting_reference_image'
            return
        
        process_reference_task(bot, message, user_id, message.text)
    
    @bot.message_handler(
        content_types=['photo'],
        func=lambda message: tool_states.get(message.from_user.id) == 'waiting_reference_choice'
    )
    def handle_reference_target_photo(message):
        """Пользователь отправил фото — трансформируем в стиль референса"""
        user_id = message.from_user.id
        
        if user_id not in reference_images:
            bot.send_message(
                message.chat.id,
                '❌ Референс не найден. Загрузите изображение заново.',
                reply_markup=get_tool_back_keyboard(),
                parse_mode='HTML'
            )
            tool_states[user_id] = 'waiting_reference_image'
            return
        
        reference_target_images[user_id] = message.photo[-1].file_id
        process_transform_task(bot, message, user_id)
    
    @bot.message_handler(
        content_types=['document'],
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_reference_choice'
            and message.document
            and is_image_document(message.document)
        )
    )
    def handle_reference_target_document(message):
        """Пользователь отправил документ — трансформируем в стиль референса"""
        user_id = message.from_user.id
        
        if user_id not in reference_images:
            bot.send_message(
                message.chat.id,
                '❌ Референс не найден. Загрузите изображение заново.',
                reply_markup=get_tool_back_keyboard(),
                parse_mode='HTML'
            )
            tool_states[user_id] = 'waiting_reference_image'
            return
        
        reference_target_images[user_id] = message.document.file_id
        process_transform_task(bot, message, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == 'reference_same')
    def reference_same_callback(call):
        """Генерация с тем же референсом"""
        user_id = call.from_user.id
        
        if user_id not in reference_images:
            bot.answer_callback_query(call.id, "❌ Референс не найден, загрузите новый")
            tool_reference_callback(call)
            return
        
        bot.edit_message_text(
            (
                "🖼 <b>Используем тот же референс</b>\n\n"
                "Опишите, что хотите сгенерировать:"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_tool_back_keyboard(),
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_reference_prompt'
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_reference_prompt'
            and message.text
            and not message.text.startswith('/')
        )
    )
    def handle_reference_prompt(message):
        """Обработка промпта для генерации по референсу"""
        user_id = message.from_user.id
        
        if user_id not in reference_images:
            bot.send_message(
                message.chat.id,
                '❌ Референс не найден. Загрузите изображение заново.',
                reply_markup=get_tool_back_keyboard(),
                parse_mode='HTML'
            )
            tool_states[user_id] = 'waiting_reference_image'
            return
        
        process_reference_task(bot, message, user_id, message.text)

    # ============ БАННЕРЫ ============
    
    @bot.callback_query_handler(func=lambda call: call.data == 'tool_banners')
    def tool_banners_callback(call):
        """Инструмент создания баннеров"""
        user_id = call.from_user.id
        
        banner_data[user_id] = {}
        
        bot.edit_message_text(
            (
                "📢 <b>Маркетинговые баннеры</b>\n\n"
                "Создайте профессиональный баннер для соцсетей и рекламы.\n\n"
                "🎯 Выберите формат:\n\n"
                "💎 Стоимость: 1 генерация"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_banner_format_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('banner_'))
    def banner_format_callback(call):
        """Выбор формата баннера"""
        user_id = call.from_user.id
        format_key = call.data.replace('banner_', '')
        
        format_map = {
            '9:16': {'ratio': '9:16', 'name': 'Stories (1080×1920)'},
            '1:1': {'ratio': '1:1', 'name': 'Пост Instagram (1080×1080)'},
            '16:9': {'ratio': '16:9', 'name': 'Обложка Facebook (1200×630)'},
            '16:9_yt': {'ratio': '16:9', 'name': 'YouTube превью (1280×720)'},
            '1:1_product': {'ratio': '1:1', 'name': 'Товарный баннер (800×800)'},
            '21:9': {'ratio': '21:9', 'name': 'Широкий баннер (1200×300)'}
        }
        
        format_info = format_map.get(format_key, format_map['1:1'])
        
        if user_id not in banner_data:
            banner_data[user_id] = {}
        
        banner_data[user_id]['format'] = format_info['ratio']
        banner_data[user_id]['format_name'] = format_info['name']
        
        bot.edit_message_text(
            (
                f"📢 <b>Создание баннера</b>\n\n"
                f"📐 Формат: {format_info['name']}\n\n"
                f"🎨 Выберите стиль:"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_banner_style_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('bstyle_'))
    def banner_style_callback(call):
        """Выбор стиля баннера"""
        user_id = call.from_user.id
        style_key = call.data.replace('bstyle_', '')
        
        style_map = {
            'minimal': {'name': '✨ Минимализм', 'prompt': 'minimalist clean design, lots of white space, simple elegant typography, subtle colors'},
            'vibrant': {'name': '🎨 Яркий', 'prompt': 'vibrant bold colors, eye-catching design, dynamic composition, energetic mood'},
            'premium': {'name': '👔 Премиум', 'prompt': 'luxury premium design, gold accents, elegant sophisticated look, high-end aesthetic'},
            'festive': {'name': '🎉 Праздничный', 'prompt': 'festive celebration design, confetti, bright cheerful colors, party mood'},
            'eco': {'name': '🌿 Эко/Натуральный', 'prompt': 'natural organic design, green earth tones, eco-friendly aesthetic, botanical elements'},
            'tech': {'name': '⚡ Технологичный', 'prompt': 'futuristic tech design, neon glow, digital aesthetic, modern sleek look, cyber elements'}
        }
        
        style_info = style_map.get(style_key, style_map['minimal'])
        
        if user_id not in banner_data:
            banner_data[user_id] = {'format': '1:1', 'format_name': 'Квадрат'}
        
        banner_data[user_id]['style'] = style_info['prompt']
        banner_data[user_id]['style_name'] = style_info['name']
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='tool_banners'))
        
        bot.edit_message_text(
            (
                f"📢 <b>Создание баннера</b>\n\n"
                f"📐 Формат: {banner_data[user_id]['format_name']}\n"
                f"🎨 Стиль: {style_info['name']}\n\n"
                f"📝 Теперь опишите ваш баннер:\n\n"
                f"<i>Что рекламируем, какой текст на баннере, основные элементы</i>\n\n"
                f"Пример: «Скидка 50% на кофе, текст SALE, чашка кофе с паром»"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_banner_prompt'
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'banner_same')
    def banner_same_callback(call):
        """Генерация ещё одного баннера с теми же настройками"""
        user_id = call.from_user.id
        
        if user_id not in banner_data:
            bot.answer_callback_query(call.id, "❌ Настройки потеряны, начните заново")
            tool_banners_callback(call)
            return
        
        data = banner_data[user_id]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='tool_banners'))
        
        bot.edit_message_text(
            (
                f"📢 <b>Создание баннера</b>\n\n"
                f"📐 Формат: {data.get('format_name', '—')}\n"
                f"🎨 Стиль: {data.get('style_name', '—')}\n\n"
                f"📝 Опишите новый баннер:"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        tool_states[user_id] = 'waiting_banner_prompt'
        bot.answer_callback_query(call.id)

    @bot.message_handler(
        func=lambda message: (
            tool_states.get(message.from_user.id) == 'waiting_banner_prompt'
            and message.text
            and not message.text.startswith('/')
        )
    )
    def handle_banner_prompt(message):
        """Обработка промпта для баннера"""
        user_id = message.from_user.id
        
        if user_id not in banner_data:
            bot.send_message(
                message.chat.id,
                '❌ Данные потеряны. Начните заново.',
                reply_markup=get_tools_keyboard(),
                parse_mode='HTML'
            )
            if user_id in tool_states:
                del tool_states[user_id]
            return
        
        process_banner_task(bot, message, user_id, message.text)


# ============ ФУНКЦИИ СОЗДАНИЯ ЗАДАЧ ============

def process_remove_bg_task(bot, message, file_id):
    """Создаёт задачу удаления фона"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    cost = 1
    from utils.db_utils import get_user_model
    model, _ = get_user_model(user_id)
    
    balance = get_balance(user_id)
    if balance < cost:
        cleanup_user_tool_state(user_id)
        bot.send_message(
            chat_id,
            f'❌ <b>Недостаточно генераций!</b>\n\nНужно: {cost}, у вас: {balance}',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        return
    
    try:
        task_id = create_task(
            user_id=user_id,
            chat_id=chat_id,
            task_type='remove_bg',
            model=model,
            cost=cost,
            image_file_id=file_id
        )
        
        bot.send_message(
            chat_id,
            '⏳ <b>Задача создана!</b>\n\n'
            '🔮 Удаляем фон...\n'
            '💎 Стоимость: 1 генерация\n\n'
            'Результат будет отправлен автоматически.',
            parse_mode='HTML'
        )
        
        cleanup_user_tool_state(user_id)
        
    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}', parse_mode='HTML')


def process_upscale_task(bot, message, file_id):
    """Создаёт задачу апскейла"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    cost = 1
    from utils.db_utils import get_user_model
    model, _ = get_user_model(user_id)
    
    balance = get_balance(user_id)
    if balance < cost:
        cleanup_user_tool_state(user_id)
        bot.send_message(
            chat_id,
            f'❌ <b>Недостаточно генераций!</b>\n\nНужно: {cost}, у вас: {balance}',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        return
    
    try:
        task_id = create_task(
            user_id=user_id,
            chat_id=chat_id,
            task_type='upscale',
            model=model,
            cost=cost,
            image_file_id=file_id
        )
        
        bot.send_message(
            chat_id,
            '⏳ <b>Задача создана!</b>\n\n'
            '📈 Улучшаем качество...\n'
            '💎 Стоимость: 1 генерация\n\n'
            'Результат будет отправлен автоматически.',
            parse_mode='HTML'
        )
        
        cleanup_user_tool_state(user_id)
        
    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}', parse_mode='HTML')


def process_stylize_task(bot, message, user_id, file_id, style, style_name):
    """Создаёт задачу стилизации"""
    chat_id = message.chat.id
    
    model, _ = get_user_model(user_id)
    cost = get_model_cost(model)
    
    balance = get_balance(user_id)
    if balance < cost:
        cleanup_user_tool_state(user_id)
        bot.send_message(
            chat_id,
            f'❌ <b>Недостаточно генераций!</b>\n\nНужно: {cost}, у вас: {balance}',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        return
    
    try:
        task_id = create_task(
            user_id=user_id,
            chat_id=chat_id,
            task_type='stylize',
            model=model,
            style=style,
            cost=cost,
            image_file_id=file_id,
            extra_data={'style_name': style_name}
        )
        
        model_display = get_model_display_name(model)
        
        bot.send_message(
            chat_id,
            f'⏳ <b>Задача создана!</b>\n\n'
            f'🎨 Стиль: {style_name}\n'
            f'🤖 Модель: {model_display}\n'
            f'💎 Стоимость: {cost} генераций\n\n'
            f'Результат будет отправлен автоматически.',
            parse_mode='HTML'
        )
        
        # Не удаляем tool_images — может понадобиться для повторной стилизации
        if user_id in tool_states:
            del tool_states[user_id]
        
    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}', parse_mode='HTML')


def process_reference_task(bot, message, user_id, prompt):
    """Создаёт задачу генерации по референсу"""
    chat_id = message.chat.id
    
    model, _ = get_user_model(user_id)
    cost = get_model_cost(model)
    
    balance = get_balance(user_id)
    if balance < cost:
        cleanup_user_tool_state(user_id)
        bot.send_message(
            chat_id,
            f'❌ <b>Недостаточно генераций!</b>\n\nНужно: {cost}, у вас: {balance}',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        return
    
    try:
        task_id = create_task(
            user_id=user_id,
            chat_id=chat_id,
            task_type='reference',
            model=model,
            prompt=prompt,
            cost=cost,
            image_file_id=reference_images[user_id]
        )
        
        model_display = get_model_display_name(model)
        
        bot.send_message(
            chat_id,
            f'⏳ <b>Задача создана!</b>\n\n'
            f'📝 Промпт: {prompt[:100]}...\n'
            f'🤖 Модель: {model_display}\n'
            f'💎 Стоимость: {cost} генераций\n\n'
            f'Результат будет отправлен автоматически.',
            parse_mode='HTML'
        )
        
        # Не удаляем reference_images — может понадобиться для повторной генерации
        if user_id in tool_states:
            del tool_states[user_id]
        
    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}', parse_mode='HTML')


def process_transform_task(bot, message, user_id):
    """Создаёт задачу трансформации по референсу"""
    chat_id = message.chat.id
    
    model, _ = get_user_model(user_id)
    cost = get_model_cost(model)
    
    balance = get_balance(user_id)
    if balance < cost:
        cleanup_user_tool_state(user_id)
        bot.send_message(
            chat_id,
            f'❌ <b>Недостаточно генераций!</b>\n\nНужно: {cost}, у вас: {balance}',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        return
    
    try:
        task_id = create_task(
            user_id=user_id,
            chat_id=chat_id,
            task_type='transform',
            model=model,
            cost=cost,
            image_file_id=reference_images[user_id],
            image2_file_id=reference_target_images[user_id]
        )
        
        model_display = get_model_display_name(model)
        
        bot.send_message(
            chat_id,
            f'⏳ <b>Задача создана!</b>\n\n'
            f'🖼 Трансформируем в стиль референса...\n'
            f'🤖 Модель: {model_display}\n'
            f'💎 Стоимость: {cost} генераций\n\n'
            f'Результат будет отправлен автоматически.',
            parse_mode='HTML'
        )
        
        # Очищаем target, но сохраняем reference
        if user_id in reference_target_images:
            del reference_target_images[user_id]
        if user_id in tool_states:
            del tool_states[user_id]
        
    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}', parse_mode='HTML')


def process_banner_task(bot, message, user_id, prompt):
    """Создаёт задачу генерации баннера"""
    chat_id = message.chat.id
    cost = 1
    
    balance = get_balance(user_id)
    if balance < cost:
        cleanup_user_tool_state(user_id)
        bot.send_message(
            chat_id,
            f'❌ <b>Недостаточно генераций!</b>\n\nНужно: {cost}, у вас: {balance}',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        return
    
    data = banner_data.get(user_id, {})
    
    try:
        task_id = create_task(
            user_id=user_id,
            chat_id=chat_id,
            task_type='banner',
            prompt=prompt,
            aspect_ratio=data.get('format', '1:1'),
            cost=cost,
            extra_data={
                'style_prompt': data.get('style', ''),
                'format_name': data.get('format_name', ''),
                'style_name': data.get('style_name', '')
            }
        )
        
        bot.send_message(
            chat_id,
            f'⏳ <b>Задача создана!</b>\n\n'
            f'📢 Создаём баннер...\n'
            f'📐 Формат: {data.get("format_name", "—")}\n'
            f'🎨 Стиль: {data.get("style_name", "—")}\n'
            f'💎 Стоимость: 1 генерация\n\n'
            f'Результат будет отправлен автоматически.',
            parse_mode='HTML'
        )
        
        # Не удаляем banner_data — может понадобиться для повторной генерации
        if user_id in tool_states:
            del tool_states[user_id]
        
    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}', parse_mode='HTML')


# ============ ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ ============

def get_after_stylize_keyboard():
    """Клавиатура после стилизации"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('🎨 Другой стиль (это же фото)', callback_data='stylize_another_style'),
        types.InlineKeyboardButton('📷 Новое фото', callback_data='tool_stylize'),
        types.InlineKeyboardButton('🛠 К инструментам', callback_data='menu_tools'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard


def get_after_reference_keyboard():
    """Клавиатура после генерации по референсу"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('🔄 Ещё с этим референсом', callback_data='reference_same'),
        types.InlineKeyboardButton('📷 Новый референс', callback_data='tool_reference'),
        types.InlineKeyboardButton('🛠 К инструментам', callback_data='menu_tools'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard


def get_after_banner_keyboard():
    """Клавиатура после генерации баннера"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('🔄 Ещё баннер (те же настройки)', callback_data='banner_same'),
        types.InlineKeyboardButton('📐 Изменить формат/стиль', callback_data='tool_banners'),
        types.InlineKeyboardButton('🛠 К инструментам', callback_data='menu_tools'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard


def get_reference_choice_keyboard():
    """Клавиатура выбора действия после загрузки референса"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('◀️ Загрузить другой референс', callback_data='tool_reference'),
        types.InlineKeyboardButton('🛠 К инструментам', callback_data='menu_tools'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    return keyboard
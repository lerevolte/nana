from keyboards.reply import get_main_menu_keyboard, get_edit_image_keyboard, get_after_edit_keyboard
from utils.db_utils import get_user_model, get_balance, decrease_balance
from utils.image_generation import get_model_display_name, edit_image
from utils.constants import BOT_SIGNATURE
from utils.closing import PAYMENTS_DISABLED

# Словарь для хранения состояния и изображений пользователя
edit_states = {}
edit_images = {}

# Поддерживаемые форматы изображений
SUPPORTED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff']
SUPPORTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff']

def is_image_document(document):
    """Проверяет, является ли документ изображением"""
    if document.mime_type and document.mime_type in SUPPORTED_MIME_TYPES:
        return True
    
    if document.file_name:
        ext = document.file_name.lower().split('.')[-1]
        if ext in SUPPORTED_IMAGE_EXTENSIONS:
            return True
    
    return False

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_edit')
    def menu_edit_callback(call):
        """Редактирование изображения"""
        user_id = call.from_user.id
        model, _ = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        edit_message = (
            f"✏️ <b>Редактирование изображения</b>\n\n"
            f"🤖 Модель: {model_display}\n\n"
            f"📷 Отправьте изображение, которое хотите отредактировать.\n\n"
            f"<i>Можно отправить как фото или как файл (jpg, png, webp и др.)</i>"
        )
        
        bot.edit_message_text(
            edit_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_edit_image_keyboard(),
            parse_mode='HTML'
        )
        
        edit_states[user_id] = 'waiting_for_image'
        # Очищаем предыдущее изображение при новом входе в редактирование
        if user_id in edit_images:
            del edit_images[user_id]
        
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'continue_edit_same')
    def continue_edit_same_callback(call):
        """Продолжить редактирование того же изображения"""
        user_id = call.from_user.id
        
        if user_id not in edit_images:
            # Если изображения нет, просим загрузить новое
            bot.answer_callback_query(call.id, "❌ Изображение не найдено, загрузите новое")
            menu_edit_callback(call)
            return
        
        model, _ = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        bot.edit_message_text(
            (
                f"✏️ <b>Продолжаем редактирование</b>\n\n"
                f"🤖 Модель: {model_display}\n\n"
                f"💡 Отправьте описание следующего изменения.\n\n"
                f"<i>Например: «Добавь облака» или «Сделай ярче»</i>"
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_edit_image_keyboard(),
            parse_mode='HTML'
        )
        
        edit_states[user_id] = 'waiting_for_edit_prompt'
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'continue_edit_new')
    def continue_edit_new_callback(call):
        """Загрузить новое изображение для редактирования"""
        user_id = call.from_user.id
        
        # Очищаем старое изображение
        if user_id in edit_images:
            del edit_images[user_id]
        
        model, _ = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        bot.edit_message_text(
            (
                f"✏️ <b>Редактирование изображения</b>\n\n"
                f"🤖 Модель: {model_display}\n\n"
                f"📷 Отправьте новое изображение для редактирования."
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_edit_image_keyboard(),
            parse_mode='HTML'
        )
        
        edit_states[user_id] = 'waiting_for_image'
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(
        content_types=['photo'],
        func=lambda message: edit_states.get(message.from_user.id) == 'waiting_for_image'
    )
    def handle_edit_photo(message):
        """Получение фото для редактирования"""
        user_id = message.from_user.id
        
        photo = message.photo[-1]
        edit_images[user_id] = {'type': 'photo', 'file_id': photo.file_id}
        
        send_prompt_request(bot, message.chat.id, user_id)
    
    @bot.message_handler(
        content_types=['document'],
        func=lambda message: (
            edit_states.get(message.from_user.id) == 'waiting_for_image'
            and message.document
            and is_image_document(message.document)
        )
    )
    def handle_edit_document(message):
        """Получение изображения-файла для редактирования"""
        user_id = message.from_user.id
        
        edit_images[user_id] = {'type': 'document', 'file_id': message.document.file_id}
        
        send_prompt_request(bot, message.chat.id, user_id)
    
    @bot.message_handler(
        func=lambda message: (
            edit_states.get(message.from_user.id) == 'waiting_for_edit_prompt' 
            and message.text 
            and not message.text.startswith('/')
        )
    )
    def handle_edit_prompt(message):
        """Обработка промпта для редактирования"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if user_id not in edit_images:
            bot.send_message(
                message.chat.id,
                '❌ Изображение не найдено. Отправьте изображение заново.',
                reply_markup=get_edit_image_keyboard(),
                parse_mode='HTML'
            )
            edit_states[user_id] = 'waiting_for_image'
            return
        
        # Получаем стоимость модели
        from utils.image_generation import get_model_cost
        model, _ = get_user_model(user_id)
        cost = get_model_cost(model)
        
        balance = get_balance(user_id)
        if balance < cost:
            del edit_states[user_id]
            if user_id in edit_images:
                del edit_images[user_id]
            
            bot.send_message(
                message.chat.id,
                f'❌ <b>Недостаточно генераций!</b>\n\n'
                f'Для этой модели нужно: {cost} генераций\n'
                f'Ваш баланс: {balance} генераций\n\n'
                (f'Покупка генераций в этом боте больше недоступна.' if PAYMENTS_DISABLED else f'Используйте кнопку «💰 Купить» для пополнения баланса.'),
                reply_markup=get_main_menu_keyboard(),
                parse_mode='HTML'
            )
            return
        
        prompt = message.text
        image_file_id = edit_images[user_id]['file_id']
        
        # Создаём задачу
        from utils.task_queue import create_task
        
        try:
            task_id = create_task(
                user_id=user_id,
                chat_id=chat_id,
                task_type='edit',
                model=model,
                prompt=prompt,
                cost=cost,
                image_file_id=image_file_id
            )
            
            from utils.image_generation import get_model_display_name
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
            
            # Очищаем состояние
            del edit_states[user_id]
            # НЕ удаляем edit_images — может понадобиться для продолжения
            
        except Exception as e:
            bot.send_message(
                chat_id,
                f'❌ <b>Ошибка</b>\n\n{str(e)}',
                parse_mode='HTML'
            )
    
    @bot.callback_query_handler(func=lambda call: call.data == 'cancel_edit')
    def cancel_edit_callback(call):
        """Отмена редактирования и возврат в меню"""
        user_id = call.from_user.id
        
        if user_id in edit_states:
            del edit_states[user_id]
        if user_id in edit_images:
            del edit_images[user_id]
        
        balance = get_balance(user_id)
        
        bot.edit_message_text(
            f'💎 Ваш баланс: <b>{balance}</b> генераций\n\nВыберите действие:',
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)


def send_prompt_request(bot, chat_id, user_id):
    """Отправляет запрос на ввод промпта"""
    model, _ = get_user_model(user_id)
    model_display = get_model_display_name(model)
    
    bot.send_message(
        chat_id,
        (
            f"✅ <b>Изображение получено!</b>\n\n"
            f"🤖 Модель: {model_display}\n\n"
            f"💡 Теперь отправьте текстовое описание того, что нужно изменить.\n\n"
            f"<i>Например: «Сделай фон красным» или «Добавь шляпу»</i>"
        ),
        reply_markup=get_edit_image_keyboard(),
        parse_mode='HTML'
    )
    
    edit_states[user_id] = 'waiting_for_edit_prompt'
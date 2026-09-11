from keyboards.reply import get_main_menu_keyboard, get_create_image_keyboard, get_after_generation_keyboard
from utils.db_utils import get_user_model, get_balance
from utils.image_generation import get_model_display_name, get_model_cost
from utils.constants import BOT_SIGNATURE
from utils.closing import PAYMENTS_DISABLED
from utils.task_queue import create_task

# Словарь для хранения состояния пользователя (в памяти, для быстрого доступа)
user_states = {}
user_enhance_settings = {}

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data == 'toggle_enhance')
    def toggle_enhance_callback(call):
        """Переключение улучшения промпта"""
        user_id = call.from_user.id
        
        current = user_enhance_settings.get(user_id, True)
        user_enhance_settings[user_id] = not current
        new_status = user_enhance_settings[user_id]
        
        status_text = "включено ✨" if new_status else "выключено"
        bot.answer_callback_query(call.id, f"Улучшение промпта {status_text}")
        
        model, aspect_ratio = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        create_message = (
            f"🎨 <b>Генерация изображения</b>\n\n"
            f"🤖 Модель: {model_display}\n"
            f"📐 Формат: {aspect_ratio}\n\n"
            f"💡 Отправьте текстовое описание изображения, которое хотите создать."
        )
        
        bot.edit_message_text(
            create_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_create_image_keyboard(aspect_ratio, new_status),
            parse_mode='HTML'
        )
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'waiting_for_prompt' and message.text and not message.text.startswith('/'))
    def handle_prompt(message):
        """Обработка промпта для генерации — создаёт задачу в очереди"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Получаем модель и её стоимость
        model, aspect_ratio = get_user_model(user_id)
        cost = get_model_cost(model)
        
        balance = get_balance(user_id)
        if balance < cost:
            del user_states[user_id]
            
            bot.send_message(
                chat_id,
                f'❌ <b>Недостаточно генераций!</b>\n\n'
                f'Для этой модели нужно: {cost} генераций\n'
                f'Ваш баланс: {balance} генераций\n\n'
                + (f'Покупка генераций в этом боте больше недоступна.' if PAYMENTS_DISABLED else f'Используйте кнопку «💰 Купить» для пополнения баланса.'),
                reply_markup=get_main_menu_keyboard(),
                parse_mode='HTML'
            )
            return
        
        prompt = message.text
        
        # Создаём задачу в очереди
        try:
            task_id = create_task(
                user_id=user_id,
                chat_id=chat_id,
                task_type='generate',
                model=model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                cost=cost
            )
            
            model_display = get_model_display_name(model)
            
            bot.send_message(
                chat_id,
                f'⏳ <b>Задача создана!</b>\n\n'
                f'📝 Промпт: {prompt[:100]}...\n'
                f'🤖 Модель: {model_display}\n'
                f'💎 Стоимость: {cost} генераций\n\n'
                f'Изображение будет отправлено автоматически.',
                parse_mode='HTML'
            )
            
            # Очищаем состояние
            del user_states[user_id]
            
        except Exception as e:
            bot.send_message(
                chat_id,
                f'❌ <b>Ошибка создания задачи</b>\n\n{str(e)}',
                parse_mode='HTML'
            )
            print(f'Ошибка создания задачи: {e}')

    @bot.callback_query_handler(func=lambda call: call.data.startswith('try_model_'))
    def try_another_model_callback(call):
        """Попробовать генерацию с другой моделью"""
        user_id = call.from_user.id
        new_model = call.data.replace('try_model_', '')
        
        from utils.db_utils import update_user_model
        update_user_model(user_id, new_model)
        
        _, aspect_ratio = get_user_model(user_id)
        enhance_enabled = user_enhance_settings.get(user_id, True)
        
        model_display = get_model_display_name(new_model)
        cost = get_model_cost(new_model)
        
        bot.edit_message_text(
            (
                f"🎨 <b>Генерация изображения</b>\n\n"
                f"🤖 Модель: {model_display}\n"
                f"📐 Формат: {aspect_ratio}\n"
                f"💎 Стоимость: {cost} генераций\n\n"
                f"💡 Отправьте тот же или новый промпт для генерации."
            ),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_create_image_keyboard(aspect_ratio, enhance_enabled),
            parse_mode='HTML'
        )
        
        user_states[user_id] = 'waiting_for_prompt'
        bot.answer_callback_query(call.id, f'✅ Модель изменена на {model_display}')
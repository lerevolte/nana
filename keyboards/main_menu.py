from keyboards.main_menu import get_main_menu_keyboard
from keyboards.info import get_info_keyboard
from keyboards.payment import get_buy_keyboard
from utils.closing import PAYMENTS_DISABLED, payments_closed_message
from utils.db_utils import get_user_model, get_balance
from utils.image_generation import get_model_display_name

def register_handlers(bot):
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_create')
    def menu_create_callback(call):
        """Переход к созданию изображения"""
        user_id = call.from_user.id
        model, aspect_ratio = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        from keyboards.reply import get_create_image_inline_keyboard
        from handlers.create_image import user_states
        
        create_message = f"""🎨 <b>Генерация изображения</b>

🤖 Модель: {model_display}
📐 Формат: {aspect_ratio}

💡 Отправьте текстовое описание изображения, которое хотите создать."""
        
        bot.edit_message_text(
            create_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_create_image_inline_keyboard(aspect_ratio),
            parse_mode='HTML'
        )
        
        # Устанавливаем состояние ожидания промпта
        user_states[user_id] = 'waiting_for_prompt'
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_edit')
    def menu_edit_callback(call):
        """Редактирование изображения"""
        bot.answer_callback_query(call.id, '✏️ Функция редактирования будет доступна позже!', show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_model')
    def menu_model_callback(call):
        """Выбор модели"""
        from keyboards.inline import get_model_selection_keyboard
        from utils.db_utils import get_user_model
        
        user_id = call.from_user.id
        current_model, _ = get_user_model(user_id)
        
        # Находим индекс текущей модели
        from keyboards.inline import get_models_info
        models = get_models_info()
        current_page = 0
        for i, model in enumerate(models):
            if model['id'] == current_model:
                current_page = i
                break
        
        keyboard, model_info = get_model_selection_keyboard(current_page, current_model)
        
        # Проверяем, активна ли эта модель
        is_active = model_info['id'] == current_model
        status = "✅ Эта модель сейчас активна для всех ваших генераций." if is_active else ""
        
        message_text = f"""**{model_info['name']}**

{model_info['description']}

{status}"""
        
        bot.edit_message_text(
            message_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_buy')
    def menu_buy_callback(call):
        """Покупка генераций"""
        if PAYMENTS_DISABLED:
            text, keyboard = payments_closed_message(call.from_user.id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            bot.answer_callback_query(call.id)
            return
        user_id = call.from_user.id
        first_name = call.from_user.first_name or 'Пользователь'
        
        buy_message = f"""💰 {first_name}, хотите больше генераций?

Ваш ID: {user_id}

🎁 Бонус при покупке любого пакета: Гайд по промптингу в подарок!

Цены:
→ 7 генераций - 150₽
→ 50 генераций - 450₽ (скидка 58%, экономия 621₽)
→ 100 генераций - 850₽ (–60%, 1293₽)
→ 150 генераций - 1230₽ (–62%, 1985₽)
→ 200 генераций - 1600₽ (–63%, 2686₽)
→ 250 генераций - 1950₽ (–64%, 3408₽)
→ 300 генераций - 2280₽ (–65%, 4149₽)

💳 Принимаем: карты, СБП, ЮMoney
✅ Токены добавляются автоматически после оплаты
❓ Если у вас проблемы с платежом, напишите менеджеру"""
        
        bot.edit_message_text(
            buy_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_buy_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_info')
    def menu_info_callback(call):
        """Информация"""
        info_message = "ℹ️ <b>Информация</b>\n\nВыберите раздел:"
        
        bot.edit_message_text(
            info_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_info_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
    def back_to_main_callback(call):
        """Возврат в главное меню"""
        balance = get_balance(call.from_user.id)
        
        bot.edit_message_text(
            f'💎 Ваш баланс: {balance} генераций\n\nВыберите действие:',
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_menu_keyboard()
        )
        bot.answer_callback_query(call.id)
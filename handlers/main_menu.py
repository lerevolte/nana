from keyboards.reply import (
    get_main_menu_keyboard, get_create_image_keyboard, 
    get_aspect_ratio_keyboard, get_tools_keyboard
)
from keyboards.info import get_info_keyboard
from keyboards.payment import get_buy_keyboard
from keyboards.inline import get_model_selection_keyboard, get_models_info
from utils.db_utils import get_user_model, get_balance
from utils.image_generation import get_model_display_name

def register_handlers(bot):
    
    # Импортируем состояния из других модулей
    from handlers.create_image import user_states, user_enhance_settings
    from handlers.edit_image import edit_states, edit_images
    from utils.state_manager import clear_user_state
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_create')
    def menu_create_callback(call):
        """Создание изображения"""
        user_id = call.from_user.id
        model, aspect_ratio = get_user_model(user_id)
        model_display = get_model_display_name(model)
        enhance_enabled = user_enhance_settings.get(user_id, True)
        
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
            reply_markup=get_create_image_keyboard(aspect_ratio, enhance_enabled),
            parse_mode='HTML'
        )
        
        user_states[user_id] = 'waiting_for_prompt'
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_tools')
    def menu_tools_callback(call):
        """Инструменты"""
        tools_message = (
            "🛠 <b>Инструменты</b>\n\n"
            "Выберите инструмент для работы с изображениями:"
        )
        
        try:
            bot.edit_message_text(
                tools_message,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_tools_keyboard(),
                parse_mode='HTML'
            )
        except Exception as e:
            # Если сообщение уже такое же — игнорируем
            if "message is not modified" not in str(e):
                print(f"Error in menu_tools_callback: {e}")
        
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_model')
    def menu_model_callback(call):
        """Выбор модели"""
        user_id = call.from_user.id
        current_model, _ = get_user_model(user_id)
        
        models = get_models_info()
        current_page = 0
        for i, model in enumerate(models):
            if model['id'] == current_model:
                current_page = i
                break
        
        keyboard, model_info = get_model_selection_keyboard(current_page, current_model)
        
        is_active = model_info['id'] == current_model
        status = "\n\n✅ Эта модель сейчас активна." if is_active else ""
        
        message_text = (
            f"🤖 <b>{model_info['name']}</b>\n\n"
            f"{model_info['description']}{status}"
        )
        
        bot.edit_message_text(
            message_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_buy')
    def menu_buy_callback(call):
        """Покупка генераций"""
        first_name = call.from_user.first_name or 'Пользователь'
        
        buy_message = (
            f"💰 <b>{first_name}, хотите больше генераций?</b>\n\n"
            f"🎁 Бонус при покупке: Гайд по промптингу в подарок!\n\n"
            f"<b>Цены:</b>\n"
            f"→ 7 генераций — 150₽\n"
            f"→ 50 генераций — 450₽ (скидка 58%)\n"
            f"→ 100 генераций — 850₽ (–60%)\n"
            f"→ 150 генераций — 1230₽ (–62%)\n"
            f"→ 200 генераций — 1600₽ (–63%)\n"
            f"→ 250 генераций — 1950₽ (–64%)\n"
            f"→ 300 генераций — 2280₽ (–65%)\n\n"
            f"💳 Принимаем: карты, СБП, ЮMoney\n"
            f"✅ Генерации добавляются автоматически"
        )
        
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
        
        user_id = call.from_user.id

        clear_user_state(user_id)
        
        bot.edit_message_text(
            f'💎 Ваш баланс: <b>{balance}</b> генераций\n\nВыберите действие:',
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'change_aspect_ratio')
    def change_aspect_ratio_callback(call):
        """Изменение формата изображения"""
        bot.edit_message_text(
            '📐 <b>Выберите формат изображения:</b>',
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_aspect_ratio_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'category_ignore')
    def category_ignore_callback(call):
        """Игнорируем нажатие на заголовки категорий"""
        bot.answer_callback_query(call.id)
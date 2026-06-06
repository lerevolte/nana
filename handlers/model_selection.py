from keyboards.inline import get_model_selection_keyboard, get_models_info
from keyboards.reply import get_main_menu_keyboard
from utils.db_utils import get_user_model, update_user_model, get_balance

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('model_page_'))
    def model_page_callback(call):
        """Переключение страниц моделей"""
        if call.data == 'model_page_info':
            bot.answer_callback_query(call.id)
            return
        
        page = int(call.data.split('_')[-1])
        user_id = call.from_user.id
        current_model, _ = get_user_model(user_id)
        
        keyboard, model_info = get_model_selection_keyboard(page, current_model)
        
        is_active = model_info['id'] == current_model
        status = "\n\n✅ Эта модель сейчас активна." if is_active else ""
        
        message_text = (
            f"🤖 <b>{model_info['name']}</b>\n\n"
            f"{model_info['description']}{status}"
        )
        
        try:
            bot.edit_message_text(
                message_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except:
            pass
        
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('select_model_'))
    def select_model_callback(call):
        """Выбор модели"""
        model_id = call.data.replace('select_model_', '')
        user_id = call.from_user.id
        
        update_user_model(user_id, model_id)
        
        models = get_models_info()
        model_name = next((m['name'] for m in models if m['id'] == model_id), model_id)
        
        bot.answer_callback_query(
            call.id, 
            f'✅ Модель "{model_name}" выбрана!',
            show_alert=True
        )
        
        # Обновляем сообщение
        current_page = 0
        for i, model in enumerate(models):
            if model['id'] == model_id:
                current_page = i
                break
        
        keyboard, model_info = get_model_selection_keyboard(current_page, model_id)
        
        message_text = (
            f"🤖 <b>{model_info['name']}</b>\n\n"
            f"{model_info['description']}\n\n"
            f"✅ Эта модель сейчас активна."
        )
        
        bot.edit_message_text(
            message_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
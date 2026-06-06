from utils.db_utils import update_user_aspect_ratio, get_user_model
from utils.image_generation import get_model_display_name
from keyboards.reply import get_create_image_keyboard, get_after_generation_keyboard


def register_handlers(bot):
    
    from handlers.create_image import user_states, user_enhance_settings
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('aspect_'))
    def aspect_ratio_callback(call):
        """Обработка выбора формата"""
        user_id = call.from_user.id
        aspect_ratio = call.data.replace('aspect_', '')
        
        update_user_aspect_ratio(user_id, aspect_ratio)
        bot.answer_callback_query(call.id, f'✅ Формат изменён на {aspect_ratio}')
        
        model, _ = get_user_model(user_id)
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
    
    @bot.callback_query_handler(func=lambda call: call.data == 'back_to_create')
    def back_to_create_callback(call):
        """Возврат к созданию изображения"""
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
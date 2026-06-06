def safe_edit_message(bot, text, chat_id, message_id, reply_markup=None, parse_mode='HTML'):
    """Безопасное редактирование сообщения (игнорирует ошибку если сообщение не изменилось)"""
    try:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        if "message is not modified" in str(e):
            return False
        raise e


def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data == 'close_message')
    def close_message_callback(call):
        """Закрывает (удаляет) сообщение"""
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            print(f"Не удалось удалить сообщение: {e}")
        
        bot.answer_callback_query(call.id)
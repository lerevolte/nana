from telebot import types

def get_info_keyboard():
    """Клавиатура раздела информации"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(
        types.InlineKeyboardButton('💎 Мой баланс', callback_data='info_balance'),
        types.InlineKeyboardButton('💰 Купить генерации', callback_data='info_buy'),
        types.InlineKeyboardButton('🎁 Реферальная программа', callback_data='info_referral'),
        types.InlineKeyboardButton('❓ Помощь', callback_data='info_help'),
        types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main')
    )
    
    return keyboard
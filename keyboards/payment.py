from telebot import types

def get_buy_keyboard():
    """Клавиатура для покупки генераций"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    packages = [
        ('💎 7 генераций — 150₽', 'buy_7_150'),
        ('💎 50 генераций — 450₽', 'buy_50_450'),
        ('💎 100 генераций — 850₽', 'buy_100_850'),
        ('💎 150 генераций — 1230₽', 'buy_150_1230'),
        ('💎 200 генераций — 1600₽', 'buy_200_1600'),
        ('💎 250 генераций — 1950₽', 'buy_250_1950'),
        ('💎 300 генераций — 2280₽', 'buy_300_2280'),
    ]
    
    for text, callback_data in packages:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    # keyboard.add(types.InlineKeyboardButton('💬 Связаться с менеджером', callback_data='contact_manager'))
    keyboard.add(types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main'))
    
    return keyboard
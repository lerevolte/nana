import os
import logging
from telebot import types

logger = logging.getLogger(__name__)

PAYMENTS_DISABLED = True

FREE_CREDITS_DISABLED = True

CLOSING_NOTICE_ENABLED = True

EXCLUDED_IDS = {154483653, 288559694, 378775277, 6231501485, 380216490, 732775002, 1173001544, 5036641031, 7105600155, 8557234549, 826271224, 8285211072, 2077441599, 5184624543}

RECIPIENTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'closing_recipients.txt')

NEW_BOT_TG = 'https://t.me/ai_prompta_bot?start=nedavinci'
NEW_BOT_MAX = 'https://max.ru/id343527239604_bot'
NEW_SITE = 'https://prompta.pro/'

CLOSING_TEXT = (
    "⚠️ <b>Бот «Не да Винчи» скоро закрывается</b>\n\n"
    "Оставшийся баланс можно потратить, но пополнить его уже нельзя.\n\n"
    "Мы перенесли всё в новый бот <b>@ai_prompta_bot</b>: картинки, видео и песни в одном месте. "
    "Переходите:\n"
    "• Telegram: @ai_prompta_bot\n"
    f"• MAX: {NEW_BOT_MAX}\n"
    f"• Сайт: {NEW_SITE}"
)

PAYMENTS_CLOSED_TEXT = (
    "💳 <b>Покупка генераций в этом боте больше недоступна</b>\n\n"
    "Оставшийся баланс можно использовать как обычно."
)

BROADCAST_TEXT = (
    "👋 Привет! Это бот «Не да Винчи».\n\n"
    "Мы закрываем этот бот. Оставшийся баланс генераций можно использовать, а вот пополнить его уже нельзя.\n\n"
    "Всё лучшее мы собрали в новом боте <b>@ai_prompta_bot</b>: генерация картинок, видео и песен в одном месте, "
    "новые модели и удобный редактор.\n\n"
    "Переходите по любой ссылке:\n"
    "• Telegram: @ai_prompta_bot\n"
    f"• MAX: {NEW_BOT_MAX}\n"
    f"• Сайт: {NEW_SITE}\n\n"
    "Спасибо, что были с нами 💛"
)

_recipients_cache = {'mtime': None, 'ids': set()}


def load_recipients():
    try:
        mtime = os.path.getmtime(RECIPIENTS_FILE)
    except OSError:
        return set()
    if _recipients_cache['mtime'] != mtime:
        ids = set()
        with open(RECIPIENTS_FILE, encoding='utf-8') as f:
            for line in f:
                value = line.strip().split(';')[0].split(',')[0].strip()
                if value.isdigit():
                    ids.add(int(value))
        _recipients_cache['mtime'] = mtime
        _recipients_cache['ids'] = ids - EXCLUDED_IDS
        logger.info(f"[Closing] Loaded {len(_recipients_cache['ids'])} recipients")
    return _recipients_cache['ids']


def is_closing_recipient(user_id):
    return CLOSING_NOTICE_ENABLED and user_id not in EXCLUDED_IDS


def get_closing_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton('🚀 Новый бот в Telegram', url=NEW_BOT_TG))
    keyboard.add(types.InlineKeyboardButton('💬 Новый бот в MAX', url=NEW_BOT_MAX))
    keyboard.add(types.InlineKeyboardButton('🌐 Сайт prompta.pro', url=NEW_SITE))
    return keyboard


def send_closing_notice(bot, chat_id, user_id):
    if not is_closing_recipient(user_id):
        return False
    try:
        bot.send_message(chat_id, CLOSING_TEXT, reply_markup=get_closing_keyboard(), parse_mode='HTML')
        return True
    except Exception as e:
        logger.warning(f"[Closing] Failed to send notice to {user_id}: {e}")
        return False


def payments_closed_message(user_id):
    if is_closing_recipient(user_id):
        return CLOSING_TEXT, get_closing_keyboard()
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main'))
    return PAYMENTS_CLOSED_TEXT, keyboard

from keyboards.info import get_info_keyboard
from keyboards.payment import get_buy_keyboard
from keyboards.reply import get_main_menu_keyboard
from utils.db_utils import get_balance, get_or_set_referral_code, get_referral_stats
from telebot import types
import os

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data == 'info_balance')
    def info_balance_callback(call):
        """Показать баланс"""
        user_id = call.from_user.id
        balance = get_balance(user_id)
        
        from config.database import get_moscow_time
        moscow_now = get_moscow_time()
        
        balance_message = (
            f"💎 <b>Ваш баланс</b>\n\n"
            f"Доступно генераций: <b>{balance}</b>\n\n"
            f"💰 Для покупки дополнительных генераций используйте раздел «Купить генерации»\n"
            f"🎁 Приглашайте друзей и получайте бонусы!"
        )
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_info'))
        
        bot.edit_message_text(
            balance_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'info_buy')
    def info_buy_callback(call):
        """Покупка из раздела информации"""
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
    
    @bot.callback_query_handler(func=lambda call: call.data == 'info_referral')
    def info_referral_callback(call):
        """Реферальная программа"""
        user_id = call.from_user.id
        bot_username = bot.get_me().username
        
        referral_code = get_or_set_referral_code(user_id)
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
        referrals_count = get_referral_stats(user_id)
        
        referral_message = (
            f"🎁 <b>Реферальная программа</b>\n\n"
            f"Приглашай друзей и получай <b>3 бесплатные генерации</b> за каждого!\n\n"
            f"📊 <b>Ваша статистика:</b>\n"
            f"• Приглашено друзей: {referrals_count}\n"
            f"• Заработано генераций: {referrals_count * 3}\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"Отправьте эту ссылку друзьям. Когда они запустят бота, вы получите бонус!"
        )
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_info'))
        
        bot.edit_message_text(
            referral_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'info_help')
    def info_help_callback(call):
        """Справка"""
        manager_username = os.getenv('MANAGER_USERNAME', 'lerevolte1')
        
        help_message = (
            f"❓ <b>Справка по использованию</b>\n\n"
            f"<b>Основные команды:</b>\n"
            f"/start — Запуск бота\n"
            f"/menu — Главное меню\n\n"
            f"<b>Как использовать:</b>\n\n"
            f"1️⃣ <b>Создание изображения:</b>\n"
            f"Нажмите «🎨 Создать», выберите формат и отправьте описание.\n\n"
            f"2️⃣ <b>Выбор модели:</b>\n"
            f"В разделе «🤖 Модель» доступны 3 AI модели.\n\n"
            f"3️⃣ <b>Форматы:</b>\n"
            f"Квадрат, Портрет, Альбом — разные соотношения сторон.\n\n"
            f"<b>Лимиты:</b>\n"
            f"• Формат вывода: PNG\n\n"
            f"<b>Поддержка:</b> @{manager_username}"
        )
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_info'))
        
        bot.edit_message_text(
            help_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'back_to_info')
    def back_to_info_callback(call):
        """Назад к информации"""
        info_message = "ℹ️ <b>Информация</b>\n\nВыберите раздел:"
        
        bot.edit_message_text(
            info_message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_info_keyboard(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
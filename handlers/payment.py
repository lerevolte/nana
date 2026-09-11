from keyboards.payment import get_buy_keyboard
from keyboards.reply import get_main_menu_keyboard
from utils.db_utils import get_balance, create_payment, update_user_contact, get_or_create_user
from utils.yookassa_service import create_payment as create_yookassa_payment
from telebot import types
import os
from utils.closing import PAYMENTS_DISABLED, payments_closed_message

PACKAGES = {
    'buy_7_150': {'generations': 7, 'price': 150},
    'buy_50_450': {'generations': 50, 'price': 450},
    'buy_100_850': {'generations': 100, 'price': 850},
    'buy_150_1230': {'generations': 150, 'price': 1230},
    'buy_200_1600': {'generations': 200, 'price': 1600},
    'buy_250_1950': {'generations': 250, 'price': 1950},
    'buy_300_2280': {'generations': 300, 'price': 2280},
}

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
    def package_selection_callback(call):
        """Выбор пакета для покупки"""
        package_key = call.data
        
        if package_key not in PACKAGES:
            bot.answer_callback_query(call.id, '❌ Неверный пакет')
            return
        
        package = PACKAGES[package_key]
        user_id = call.from_user.id

        if PAYMENTS_DISABLED:
            text, keyboard = payments_closed_message(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            bot.answer_callback_query(call.id)
            return

        user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)
        saved_contact = user.get('contact')
        
        if saved_contact:
            # Есть сохранённый контакт — сразу создаём платёж
            bot.edit_message_text(
                '⏳ Создаём ссылку на оплату...',
                call.message.chat.id,
                call.message.message_id
            )
            
            result = create_yookassa_payment(
                user_id, 
                package['generations'],
                user_contact=saved_contact,
                custom_price=package['price']
            )
            
            if not result["success"]:
                if result.get("error") == "invalid_contact":
                    update_user_contact(user_id, None)
                    request_contact(bot, call.message, package, user_id)
                    return
                
                bot.edit_message_text(
                    f"❌ Ошибка: {result.get('error')}", 
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_buy_keyboard()
                )
                return
            
            create_payment(user_id, result["payment_id"], package['price'], package['generations'])
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                text="💳 Оплатить", 
                url=result['payment_url']
            ))
            keyboard.add(types.InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="back_to_buy"
            ))
            
            bot.edit_message_text(
                (
                    f"✅ <b>Счёт сформирован</b>\n\n"
                    f"Пакет: <b>{package['generations']} генераций</b>\n"
                    f"Сумма: <b>{package['price']}₽</b>\n\n"
                    f"Нажмите кнопку ниже для оплаты.\n"
                    f"После оплаты генерации добавятся автоматически."
                ),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            bot.answer_callback_query(call.id)
            return
        
        # Контакта нет — запрашиваем
        request_contact(bot, call.message, package, user_id)
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'back_to_buy')
    def back_to_buy_callback(call):
        """Назад к выбору пакета"""
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
    
    @bot.callback_query_handler(func=lambda call: call.data == 'contact_manager')
    def contact_manager_callback(call):
        """Связь с менеджером"""
        user_id = call.from_user.id
        manager_username = os.getenv('MANAGER_USERNAME', 'lerevolte1')
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(
            f'💬 Написать @{manager_username}',
            url=f'https://t.me/{manager_username}'
        ))
        keyboard.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_buy'))
        
        message_text = (
            f"💬 <b>Связь с менеджером</b>\n\n"
            f"Если у вас возникли вопросы по оплате, напишите менеджеру.\n\n"
            f"Ваш ID: <code>{user_id}</code>\n"
            f"Скопируйте ID и отправьте его менеджеру."
        )
        
        bot.edit_message_text(
            message_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)


def request_contact(bot, message, package, user_id):
    """Запрос контакта для чека"""
    # Сохраняем данные о пакете
    bot.edit_message_text(
        (
            "🧾 <b>Для отправки чека введите Email или телефон</b>\n\n"
            "Например: mymail@gmail.com или +79001234567"
        ),
        message.chat.id,
        message.message_id,
        parse_mode='HTML'
    )
    
    bot.register_next_step_handler(message, lambda msg: process_contact(bot, msg, package))


def process_contact(bot, message, package):
    """Обработка введённого контакта"""
    contact = message.text.strip()
    user_id = message.from_user.id
    
    # Валидация
    is_email = '@' in contact and '.' in contact.split('@')[-1]
    digits = ''.join(filter(str.isdigit, contact))
    is_phone = len(digits) >= 10
    
    if not is_email and not is_phone:
        msg = bot.send_message(
            message.chat.id,
            (
                "❌ <b>Некорректный формат</b>\n\n"
                "Введите Email (например: mymail@gmail.com)\n"
                "или телефон (например: +79001234567)"
            ),
            parse_mode='HTML'
        )
        bot.register_next_step_handler(msg, lambda m: process_contact(bot, m, package))
        return
    
    progress_msg = bot.send_message(message.chat.id, "⏳ Создаём ссылку на оплату...")
    
    result = create_yookassa_payment(
        user_id,
        package['generations'],
        user_contact=contact,
        custom_price=package['price']
    )
    
    if not result["success"]:
        if result.get("error") == "invalid_contact":
            bot.edit_message_text(
                (
                    f"❌ {result.get('message', 'Некорректный контакт')}\n\n"
                    "Попробуйте ещё раз:"
                ),
                message.chat.id,
                progress_msg.message_id,
                parse_mode='HTML'
            )
            bot.register_next_step_handler(progress_msg, lambda m: process_contact(bot, m, package))
            return
        
        bot.edit_message_text(
            f"❌ Ошибка: {result.get('error')}",
            message.chat.id,
            progress_msg.message_id
        )
        return
    
    # Сохраняем контакт и платёж
    update_user_contact(user_id, contact)
    create_payment(user_id, result["payment_id"], package['price'], package['generations'])
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(
        text="💳 Оплатить",
        url=result['payment_url']
    ))
    keyboard.add(types.InlineKeyboardButton(
        text="◀️ Главное меню",
        callback_data="back_to_main"
    ))
    
    bot.edit_message_text(
        (
            f"✅ <b>Счёт сформирован</b>\n\n"
            f"Пакет: <b>{package['generations']} генераций</b>\n"
            f"Сумма: <b>{package['price']}₽</b>\n\n"
            f"Нажмите кнопку ниже для оплаты.\n"
            f"После оплаты генерации добавятся автоматически.\n"
            f"❓ Если возникли проблемы, используйте /help"
        ),
        message.chat.id,
        progress_msg.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
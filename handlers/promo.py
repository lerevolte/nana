from telebot import types
from utils.db_utils import use_promo_code, get_balance
from keyboards.reply import get_main_menu_keyboard
from utils.state_manager import StateDict, StateDataDict

# Используем персистентные состояния
promo_states = StateDict('promo')
user_discount_promos = StateDataDict('discount_promo')

def register_handlers(bot):
    
    @bot.message_handler(func=lambda message: (
        promo_states.get(message.from_user.id) == 'waiting_promo_code'
        and message.text
        and not message.text.startswith('/')
    ))
    def handle_promo_code(message):
        """Обработка введённого промокода"""
        user_id = message.from_user.id
        code = message.text.strip().upper()
        
        # Очищаем состояние
        if user_id in promo_states:
            del promo_states[user_id]
        
        result = use_promo_code(user_id, code)
        
        if not result['success']:
            error_messages = {
                'already_used': '❌ Вы уже использовали этот промокод.',
                'not_found': '❌ Промокод не найден или неактивен.',
                'limit_reached': '❌ Лимит использований промокода исчерпан.'
            }
            error_msg = error_messages.get(result['error'], f"❌ Ошибка: {result['error']}")
            
            bot.send_message(
                message.chat.id,
                error_msg,
                reply_markup=get_main_menu_keyboard(),
                parse_mode='HTML'
            )
            return
        
        # Успешно
        if result['type'] == 'free':
            # Бесплатные генерации
            balance = get_balance(user_id)
            bot.send_message(
                message.chat.id,
                (
                    f"🎉 <b>Промокод активирован!</b>\n\n"
                    f"🎁 Вам начислено: <b>{result['generations_amount']} генераций</b>\n"
                    f"💎 Ваш баланс: <b>{balance}</b> генераций"
                ),
                reply_markup=get_main_menu_keyboard(),
                parse_mode='HTML'
            )
        
        elif result['type'] == 'discount':
            # Скидочный промокод — сохраняем для покупки
            user_discount_promos[user_id] = {
                'code': code,
                'generations': result['generations_amount'],
                'price': result['discount_price']
            }
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    f"💳 Купить {result['generations_amount']} генераций за {result['discount_price']}₽",
                    callback_data='buy_with_promo'
                )
            )
            keyboard.add(types.InlineKeyboardButton('◀️ Позже', callback_data='back_to_main'))
            
            bot.send_message(
                message.chat.id,
                (
                    f"🎉 <b>Промокод активирован!</b>\n\n"
                    f"🏷 Скидка: <b>{result['generations_amount']} генераций</b> "
                    f"за <b>{result['discount_price']}₽</b>\n\n"
                    f"Нажмите кнопку ниже, чтобы воспользоваться скидкой."
                ),
                reply_markup=keyboard,
                parse_mode='HTML'
            )
    
    @bot.callback_query_handler(func=lambda call: call.data == 'buy_with_promo')
    def buy_with_promo_callback(call):
        """Покупка со скидкой по промокоду"""
        user_id = call.from_user.id
        
        if user_id not in user_discount_promos:
            bot.answer_callback_query(call.id, "❌ Скидка истекла, введите промокод заново")
            return
        
        promo = user_discount_promos[user_id]
        
        from utils.db_utils import get_or_create_user, update_user_contact
        from utils.yookassa_service import create_payment as create_yookassa_payment
        from utils.db_utils import create_payment
        
        user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)
        saved_contact = user.get('contact')
        
        if saved_contact:
            # Создаём платёж сразу
            bot.edit_message_text(
                '⏳ Создаём ссылку на оплату...',
                call.message.chat.id,
                call.message.message_id
            )
            
            result = create_yookassa_payment(
                user_id,
                promo['generations'],
                user_contact=saved_contact,
                custom_price=promo['price']
            )
            
            if not result["success"]:
                bot.edit_message_text(
                    f"❌ Ошибка: {result.get('error')}",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_main_menu_keyboard()
                )
                return
            
            create_payment(user_id, result["payment_id"], promo['price'], promo['generations'])
            
            # Удаляем использованный промокод
            del user_discount_promos[user_id]
            
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
                    f"✅ <b>Счёт со скидкой сформирован!</b>\n\n"
                    f"🎁 Пакет: <b>{promo['generations']} генераций</b>\n"
                    f"💰 Сумма: <b>{promo['price']}₽</b>\n\n"
                    f"Нажмите кнопку для оплаты."
                ),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            # Запрашиваем контакт
            bot.edit_message_text(
                (
                    "🧾 <b>Для чека введите Email или телефон</b>\n\n"
                    "Например: mymail@gmail.com или +79001234567"
                ),
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            
            promo_states[user_id] = 'waiting_promo_contact'
        
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(func=lambda message: (
        promo_states.get(message.from_user.id) == 'waiting_promo_contact'
        and message.text
        and not message.text.startswith('/')
    ))
    def handle_promo_contact(message):
        """Обработка контакта для промо-покупки"""
        from utils.db_utils import update_user_contact, create_payment
        from utils.yookassa_service import create_payment as create_yookassa_payment
        
        user_id = message.from_user.id
        contact = message.text.strip()
        
        if user_id not in user_discount_promos:
            bot.send_message(message.chat.id, "❌ Скидка истекла, введите промокод заново")
            if user_id in promo_states:
                del promo_states[user_id]
            return
        
        promo = user_discount_promos[user_id]
        
        # Валидация
        is_email = '@' in contact and '.' in contact.split('@')[-1]
        digits = ''.join(filter(str.isdigit, contact))
        is_phone = len(digits) >= 10
        
        if not is_email and not is_phone:
            bot.send_message(
                message.chat.id,
                "❌ Некорректный формат. Введите Email или телефон:",
                parse_mode='HTML'
            )
            return
        
        progress_msg = bot.send_message(message.chat.id, "⏳ Создаём ссылку на оплату...")
        
        result = create_yookassa_payment(
            user_id,
            promo['generations'],
            user_contact=contact,
            custom_price=promo['price']
        )
        
        if not result["success"]:
            bot.edit_message_text(
                f"❌ Ошибка: {result.get('error')}",
                message.chat.id,
                progress_msg.message_id
            )
            return
        
        # Сохраняем контакт и платёж
        update_user_contact(user_id, contact)
        create_payment(user_id, result["payment_id"], promo['price'], promo['generations'])
        
        # Очищаем
        del user_discount_promos[user_id]
        if user_id in promo_states:
            del promo_states[user_id]
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="💳 Оплатить", url=result['payment_url']))
        keyboard.add(types.InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main"))
        
        bot.edit_message_text(
            (
                f"✅ <b>Счёт со скидкой сформирован!</b>\n\n"
                f"🎁 Пакет: <b>{promo['generations']} генераций</b>\n"
                f"💰 Сумма: <b>{promo['price']}₽</b>\n\n"
                f"Нажмите кнопку для оплаты."
            ),
            message.chat.id,
            progress_msg.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
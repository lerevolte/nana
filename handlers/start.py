from keyboards.reply import get_main_menu_keyboard, get_create_image_keyboard, get_edit_image_keyboard
from keyboards.info import get_info_keyboard
from keyboards.payment import get_buy_keyboard
from keyboards.inline import get_model_selection_keyboard, get_models_info
from utils.db_utils import (
    get_or_create_user, get_user_by_referral_code, add_referral,
    get_balance, get_user_model, get_or_set_referral_code, get_referral_stats
)
from utils.image_generation import get_model_display_name
from telebot import types
import os
import base64
import logging
from utils.analytics import send_analytics, send_yandex_goal
from utils.yandex_api import metrica
import time
import asyncio
import random
import threading

logger = logging.getLogger(__name__)

def run_async_background(coro):
    """Запускает асинхронную функцию в отдельном потоке, чтобы не блокировать бота"""
    def _run():
        try:
            # Создаем новый цикл событий для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
            loop.close()
        except Exception as e:
            logger.error(f"Background task error: {e}")
            
    # Запускаем в потоке-демоне (он закроется сам, если основной скрипт упадет)
    threading.Thread(target=_run, daemon=True).start()
    
def parse_start_args(args_text):
    """Парсит аргументы команды /start для извлечения UTM-меток и реферального кода"""
    utms = {
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
        "utm_term": None,
        "ym_client_id": None
    }
    referral_code = None
    
    if not args_text:
        return utms, referral_code
    
    logger.info(f"▶️ START COMMAND received. Args: {args_text}")
    
    try:
        # ПОПЫТКА 1: Компактный формат (разделитель _)
        # Пример: yandex_cpc_campaign1_content1
        if "_" in args_text and "=" not in args_text:
            parts = args_text.split("_")
            if len(parts) >= 1: utms["utm_source"] = parts[0]
            if len(parts) >= 2: utms["utm_medium"] = parts[1]
            if len(parts) >= 3: utms["utm_campaign"] = parts[2]
            if len(parts) >= 4: utms["utm_content"] = parts[3]
            if len(parts) >= 5: utms["ym_client_id"] = parts[-1]
            logger.info(f"✅ Parsed Compact UTMs: {utms}")
        
        # ПОПЫТКА 2: Base64 закодированные параметры
        elif "=" in args_text or len(args_text) > 20:
            try:
                # Пробуем декодировать Base64
                padding = len(args) % 4
                if padding:
                    args_padded = args + "=" * (4 - padding)
                else:
                    args_padded = args
                
                decoded_bytes = base64.urlsafe_b64decode(args_padded)
                decoded_str = decoded_bytes.decode("utf-8")
                
                # Если расшифровалось и похоже на параметры url (есть =)
                if "=" in decoded_str:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(decoded_str)
                    for key, values in parsed.items():
                        clean_key = key.strip()
                        if clean_key in utms and values:
                            utms[clean_key] = values[0]
                    logger.info(f"✅ Parsed Base64 UTMs: {utms}")
                else:
                    # Расшифровалось, но это просто текст (например, старая метка)
                    utms["utm_source"] = decoded_str
                    logger.info(f"✅ Decoded Base64 string: {decoded_str}")

            except (binascii.Error, UnicodeDecodeError, ValueError):
                logger.info(f"ℹ️ Start param is plain text: {args}")
                utms["utm_source"] = args
        
        # ПОПЫТКА 3: Простой текст (реферальный код или источник)
        else:
            # Проверяем, похоже ли на реферальный код
            if len(args_text) == 8 and args_text.isalnum() and args_text.isupper():
                referral_code = args_text
                logger.info(f"✅ Detected referral code: {referral_code}")
            else:
                utms["utm_source"] = args_text
                logger.info(f"✅ Set utm_source: {args_text}")
    
    except Exception as e:
        logger.error(f"⚠️ Error processing start args: {e}")
        utms["utm_source"] = args_text
    
    return utms, referral_code

def register_handlers(bot):
    
    @bot.message_handler(commands=['start'])
    def start_command(message):
        user_id = message.from_user.id
        username = message.from_user.username or ''
        first_name = message.from_user.first_name or ''
        
        # Парсим аргументы команды /start
        args_text = None
        if len(message.text.split()) > 1:
            args_text = message.text.split(maxsplit=1)[1]
        
        utms, referral_code = parse_start_args(args_text)

        try:
            ym_client_id = utms.get('ym_client_id')
            
            # 1. Отправляем цель "podpiska-na-bota"
            #if ym_client_id:
                # Запускаем фоном, чтобы не тормозить бота
            if not ym_client_id:
                # Если client_id нет, генерируем временный, но лучше сохранять реальный с сайта
                # Формат Yandex: timestamp + random
                ym_client_id = f"{int(time.time())}{random.randint(100000000, 999999999)}"
            run_async_background(
                metrica.upload_conversion(
                    client_id=ym_client_id, 
                    goal_name="podpiska-na-bota",
                    user_id=user_id
                )
            )

            # Отправляем аналитику (берем source или 'organic')
            # analytics_param = utms.get("utm_source", "organic")
            # asyncio.create_task(send_analytics(message.from_user.id, analytics_param))
        except Exception as e:
            logger.error(f"Analytics dispatch error: {e}")
        
        try:
            # Создаём/получаем пользователя с UTM-метками
            user = get_or_create_user(
                user_id=user_id, 
                username=username, 
                first_name=first_name,
                utm_source=utms.get("utm_source"),
                utm_medium=utms.get("utm_medium"),
                utm_campaign=utms.get("utm_campaign"),
                utm_content=utms.get("utm_content"),
                utm_term=utms.get("utm_term"),
                ym_client_id=utms.get("ym_client_id")
            )

            if user.get('is_new'):
                from utils.notifications import notify_new_user
                notify_new_user(
                    bot,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    referrer_id=referrer_id if referral_code else None,
                    utms=utms if any(utms.values()) else None
                )
            
            # Обработка реферального кода
            referral_bonus_message = ""
            if referral_code and not user.get('referred_by'):
                referrer_id = get_user_by_referral_code(referral_code)
                
                if referrer_id and referrer_id != user_id:
                    if add_referral(referrer_id, user_id):
                        referral_bonus_message = "\n🎉 Вы пришли по реферальной ссылке! Вашему другу начислено 3 генерации!"
                        
                        try:
                            bot.send_message(
                                referrer_id,
                                "🎁 <b>У вас новый реферал!</b>\n\n"
                                "Вам начислено 3 бесплатные генерации!",
                                parse_mode='HTML'
                            )
                        except:
                            pass
            
            # Логируем если есть UTM-метки
            if any(utms.values()):
                logger.info(f"👤 User {user_id} registered with UTMs: {utms}")
            
            welcome_message = (
                f"🎉 <b>Добро пожаловать в Не да Винчи!</b>\n\n"
                f"🎁 Твой приветственный бонус: 1 генерация\n"
                f"{referral_bonus_message}\n\n"
                f"💎 Текущий баланс: <b>{user['generations_balance']}</b> генераций\n\n"
                f"Выберите действие:"
            )
            
            bot.send_message(
                message.chat.id,
                welcome_message,
                reply_markup=get_main_menu_keyboard(),
                parse_mode='HTML'
            )
            
        except Exception as e:
            bot.send_message(message.chat.id, '❌ Произошла ошибка. Попробуйте позже.')
            print(f'Ошибка: {e}')
    
    @bot.message_handler(commands=['menu'])
    def menu_command(message):
        balance = get_balance(message.from_user.id)
        
        bot.send_message(
            message.chat.id,
            f'💎 Ваш баланс: <b>{balance}</b> генераций\n\nВыберите действие:',
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['create'])
    def create_command(message):
        from handlers.create_image import user_states
        
        user_id = message.from_user.id
        model, aspect_ratio = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        create_message = (
            f"🎨 <b>Генерация изображения</b>\n\n"
            f"🤖 Модель: {model_display}\n"
            f"📐 Формат: {aspect_ratio}\n\n"
            f"💡 Отправьте текстовое описание изображения, которое хотите создать."
        )
        
        bot.send_message(
            message.chat.id,
            create_message,
            reply_markup=get_create_image_keyboard(aspect_ratio),
            parse_mode='HTML'
        )
        
        user_states[user_id] = 'waiting_for_prompt'
    
    @bot.message_handler(commands=['edit'])
    def edit_command(message):
        """Команда /edit — редактирование изображения"""
        from handlers.edit_image import edit_states
        
        user_id = message.from_user.id
        model, _ = get_user_model(user_id)
        model_display = get_model_display_name(model)
        
        edit_message = (
            f"✏️ <b>Редактирование изображения</b>\n\n"
            f"🤖 Модель: {model_display}\n\n"
            f"📷 Отправьте изображение, которое хотите отредактировать.\n\n"
            f"<i>Можно отправить как фото или как файл (jpg, png, webp и др.)</i>"
        )
        
        bot.send_message(
            message.chat.id,
            edit_message,
            reply_markup=get_edit_image_keyboard(),
            parse_mode='HTML'
        )
        
        edit_states[user_id] = 'waiting_for_image'
    
    @bot.message_handler(commands=['model'])
    def model_command(message):
        user_id = message.from_user.id
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
        
        bot.send_message(
            message.chat.id,
            message_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['balance'])
    def balance_command(message):
        user_id = message.from_user.id
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
        keyboard.add(types.InlineKeyboardButton('💰 Купить генерации', callback_data='menu_buy'))
        keyboard.add(types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main'))
        
        bot.send_message(
            message.chat.id,
            balance_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['buy'])
    def buy_command(message):
        first_name = message.from_user.first_name or 'Пользователь'
        
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
        
        bot.send_message(
            message.chat.id,
            buy_message,
            reply_markup=get_buy_keyboard(),
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['referral'])
    def referral_command(message):
        user_id = message.from_user.id
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
        keyboard.add(types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main'))
        
        bot.send_message(
            message.chat.id,
            referral_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['help'])
    def help_command(message):
        manager_username = os.getenv('MANAGER_USERNAME', 'lerevolte1')
        
        help_message = (
            f"❓ <b>Справка по использованию</b>\n\n"
            f"<b>Основные команды:</b>\n"
            f"/start — Запуск бота\n"
            f"/menu — Главное меню\n"
            f"/create — Создать изображение\n"
            f"/edit — Редактировать изображение\n"
            f"/model — Выбрать модель\n"
            f"/balance — Мой баланс\n"
            f"/buy — Купить генерации\n"
            f"/referral — Реферальная программа\n"
            f"/help — Эта справка\n\n"
            f"<b>Как использовать:</b>\n\n"
            f"1️⃣ <b>Создание изображения:</b>\n"
            f"Нажмите «🎨 Создать», выберите формат и отправьте описание.\n\n"
            f"2️⃣ <b>Редактирование:</b>\n"
            f"Нажмите «✏️ Редактировать», отправьте фото и опишите изменения.\n\n"
            f"3️⃣ <b>Выбор модели:</b>\n"
            f"В разделе «🤖 Модель» доступны 3 AI модели.\n\n"
            f"<b>Лимиты:</b>\n"
            f"• Формат вывода: PNG\n\n"
            # f"<b>Поддержка:</b> @{manager_username}"
        )
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main'))
        
        bot.send_message(
            message.chat.id,
            help_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    @bot.message_handler(commands=['tools'])
    def tools_command(message):
        """Команда /tools — инструменты"""
        from keyboards.reply import get_tools_keyboard
        
        bot.send_message(
            message.chat.id,
            (
                "🛠 <b>Инструменты</b>\n\n"
                "Выберите инструмент для работы с изображениями:"
            ),
            reply_markup=get_tools_keyboard(),
            parse_mode='HTML'
        )

    @bot.message_handler(commands=['invite'])
    def invite_command(message):
        """Команда приглашения друзей"""
        user_id = message.from_user.id
        bot_username = bot.get_me().username
        
        referral_code = get_or_set_referral_code(user_id)
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
        from utils.db_utils import get_referral_stats_detailed
        stats = get_referral_stats_detailed(user_id)
        
        # Награда за оплатившего друга
        REFERRAL_REWARD = 5
        
        invite_message = (
            f"👥 <b>Пригласи друга — получи {REFERRAL_REWARD} генераций!</b>\n\n"
            f"Как это работает:\n"
            f"1️⃣ Отправь другу свою ссылку\n"
            f"2️⃣ Друг регистрируется по ссылке\n"
            f"3️⃣ Когда друг <b>оплатит</b> любой пакет — ты получаешь <b>{REFERRAL_REWARD} генераций</b>!\n\n"
            f"📊 <b>Твоя статистика:</b>\n"
            f"├ Приглашено друзей: {stats['total']}\n"
            f"├ Оплатили: {stats['paid']} (+{stats['paid'] * REFERRAL_REWARD} генераций)\n"
            f"└ Ожидают оплаты: {stats['pending']}\n\n"
            f"🔗 <b>Твоя ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"<i>Нажми на ссылку, чтобы скопировать</i>"
        )
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                '📤 Поделиться ссылкой', 
                url=f'https://t.me/share/url?url={referral_link}&text=Крутой бот для генерации изображений!'
            )
        )
        keyboard.add(types.InlineKeyboardButton('◀️ Главное меню', callback_data='back_to_main'))
        
        bot.send_message(
            message.chat.id,
            invite_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['promo'])
    def promo_command(message):
        """Команда ввода промокода"""
        from handlers.promo import promo_states
        
        user_id = message.from_user.id
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton('◀️ Отмена', callback_data='back_to_main'))
        
        bot.send_message(
            message.chat.id,
            (
                "🎁 <b>Введите промокод</b>\n\n"
                "Отправьте промокод, чтобы получить бонус или скидку."
            ),
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        promo_states[user_id] = 'waiting_promo_code'
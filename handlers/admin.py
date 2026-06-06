import os
import asyncio
from telebot import types
from dotenv import load_dotenv
from config.database import get_connection, get_moscow_time
from utils.db_utils import get_balance, get_or_create_user, update_block_status
from handlers.promo import promo_states


load_dotenv()

# Получаем список админов из .env
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id in ADMIN_IDS

def register_handlers(bot):
    
    # ============ КОМАНДА /admin ============
    
    @bot.message_handler(commands=['admin'])
    def cmd_admin(message):
        """Админ-панель"""
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "❌ У вас нет доступа к админ-панели.")
            return
        
        text = """🔐 <b>Админ-панель</b>

<b>Статистика:</b>
/stats — Общая статистика
/daily — Статистика за сегодня

<b>Пользователи:</b>
/userinfo ID — Информация о пользователе
/addbalance ID AMOUNT — Пополнить баланс

<b>Рассылка:</b>
/broadcast — Рассылка всем пользователям
/send ID TEXT — Отправить сообщение пользователю

<b>Система:</b>
/dbinfo — Информация о БД"""
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    
    # ============ СТАТИСТИКА ============
    
    @bot.message_handler(commands=['stats'])
    def cmd_stats(message):
        """Общая статистика"""
        if not is_admin(message.from_user.id):
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Всего пользователей
            cursor.execute("SELECT COUNT(*) as count FROM users")
            total_users = cursor.fetchone()['count']
            
            # Пользователей сегодня
            cursor.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE DATE(created_at) = CURDATE()
            """)
            users_today = cursor.fetchone()['count']
            
            # Всего генераций (сумма использованных)
            cursor.execute("""
                SELECT 
                    SUM(3 - generations_balance) as used,
                    SUM(generations_balance) as remaining
                FROM users
            """)
            gen_stats = cursor.fetchone()
            
            # Платежи
            cursor.execute("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total
                FROM payments 
                WHERE status = 'succeeded'
            """)
            payment_stats = cursor.fetchone()
            
            # Платежи сегодня
            cursor.execute("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total
                FROM payments 
                WHERE status = 'succeeded' AND DATE(created_at) = CURDATE()
            """)
            payments_today = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            moscow_now = get_moscow_time()
            
            text = f"""📊 <b>Статистика бота</b>
<i>{moscow_now.strftime('%d.%m.%Y %H:%M')} МСК</i>

👥 <b>Пользователи:</b>
├ Всего: {total_users}
└ Сегодня: {users_today}

💰 <b>Платежи (всего):</b>
├ Количество: {payment_stats['count']}
└ Сумма: {payment_stats['total']}₽

💰 <b>Платежи (сегодня):</b>
├ Количество: {payments_today['count']}
└ Сумма: {payments_today['total']}₽"""
            
            bot.send_message(message.chat.id, text, parse_mode="HTML")
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
#     @bot.message_handler(commands=['daily'])
#     def cmd_daily(message):
#         """Статистика за сегодня"""
#         if not is_admin(message.from_user.id):
#             return
        
#         try:
#             conn = get_connection()
#             cursor = conn.cursor()
            
#             # Новые пользователи по часам
#             cursor.execute("""
#                 SELECT 
#                     HOUR(created_at) as hour,
#                     COUNT(*) as count
#                 FROM users 
#                 WHERE DATE(created_at) = CURDATE()
#                 GROUP BY HOUR(created_at)
#                 ORDER BY hour
#             """)
#             hourly_users = cursor.fetchall()
            
#             # Платежи по часам
#             cursor.execute("""
#                 SELECT 
#                     HOUR(created_at) as hour,
#                     COUNT(*) as count,
#                     SUM(amount) as total
#                 FROM payments 
#                 WHERE status = 'succeeded' AND DATE(created_at) = CURDATE()
#                 GROUP BY HOUR(created_at)
#                 ORDER BY hour
#             """)
#             hourly_payments = cursor.fetchall()
            
#             cursor.close()
#             conn.close()
            
#             moscow_now = get_moscow_time()
            
#             text = f"""📅 <b>Сводка за сегодня</b>
# <i>{moscow_now.strftime('%d.%m.%Y')} МСК</i>

# 👥 <b>Новые пользователи по часам:</b>\n"""
            
#             if hourly_users:
#                 for row in hourly_users:
#                     text += f"  {row['hour']:02d}:00 — {row['count']} чел.\n"
#             else:
#                 text += "  Нет данных\n"
            
#             text += "\n💰 <b>Платежи по часам:</b>\n"
            
#             if hourly_payments:
#                 for row in hourly_payments:
#                     text += f"  {row['hour']:02d}:00 — {row['count']} шт. ({row['total']}₽)\n"
#             else:
#                 text += "  Нет платежей\n"
            
#             bot.send_message(message.chat.id, text, parse_mode="HTML")
            
#         except Exception as e:
#             bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    # ============ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ ============
    
    @bot.message_handler(commands=['userinfo'])
    def cmd_userinfo(message):
        """Информация о пользователе"""
        if not is_admin(message.from_user.id):
            return
        
        args = message.text.split()
        if len(args) < 2:
            bot.send_message(
                message.chat.id,
                "Использование: <code>/userinfo ID</code>\n\n"
                "Пример: <code>/userinfo 123456789</code>",
                parse_mode="HTML"
            )
            return
        
        try:
            user_id = int(args[1])
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID должен быть числом")
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                bot.send_message(message.chat.id, "❌ Пользователь не найден")
                cursor.close()
                conn.close()
                return
            
            # Платежи пользователя
            cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                FROM payments 
                WHERE user_id = %s AND status = 'succeeded'
            """, (user_id,))
            payments = cursor.fetchone()
            
            # Рефералы
            cursor.execute("""
                SELECT COUNT(*) as count FROM referrals WHERE referrer_id = %s
            """, (user_id,))
            referrals = cursor.fetchone()['count']
            
            cursor.close()
            conn.close()
            
            text = f"""👤 <b>Информация о пользователе</b>

🆔 ID: <code>{user_id}</code>
👤 Имя: {user.get('first_name', '-')}
📛 Username: @{user.get('username', '-') or '-'}

💎 Баланс: {user.get('generations_balance', 0)} генераций
🤖 Модель: {user.get('selected_model', '-')}
📐 Формат: {user.get('selected_aspect_ratio', '-')}

💰 Платежей: {payments['count']} на {payments['total']}₽
👥 Рефералов: {referrals}

📅 Регистрация: {str(user.get('created_at', '-'))[:19]}"""
            
            bot.send_message(message.chat.id, text, parse_mode="HTML")
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    # ============ ПОПОЛНЕНИЕ БАЛАНСА ============
    
    @bot.message_handler(commands=['addbalance'])
    def cmd_addbalance(message):
        """Пополнить баланс пользователю"""
        if not is_admin(message.from_user.id):
            return
        
        args = message.text.split()
        if len(args) < 3:
            bot.send_message(
                message.chat.id,
                "Использование: <code>/addbalance ID AMOUNT</code>\n\n"
                "Пример: <code>/addbalance 123456789 10</code>\n"
                "Для списания используйте отрицательное число.",
                parse_mode="HTML"
            )
            return
        
        try:
            user_id = int(args[1])
            amount = int(args[2])
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID и количество должны быть числами")
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Проверяем существование пользователя
            cursor.execute("SELECT generations_balance FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                bot.send_message(message.chat.id, "❌ Пользователь не найден")
                cursor.close()
                conn.close()
                return
            
            old_balance = user['generations_balance']
            new_balance = old_balance + amount
            
            cursor.execute(
                "UPDATE users SET generations_balance = %s WHERE id = %s",
                (new_balance, user_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            action = "добавлено" if amount > 0 else "списано"
            
            bot.send_message(
                message.chat.id,
                f"✅ <b>Баланс изменён!</b>\n\n"
                f"👤 Пользователь: <code>{user_id}</code>\n"
                f"💎 {action.capitalize()}: {abs(amount)} генераций\n"
                f"📊 Было: {old_balance} → Стало: {new_balance}",
                parse_mode="HTML"
            )
            
            # Уведомляем пользователя
            try:
                if amount > 0:
                    bot.send_message(
                        user_id,
                        f"🎁 <b>Вам начислено {amount} генераций!</b>\n\n"
                        f"💎 Ваш баланс: {new_balance} генераций",
                        parse_mode="HTML"
                    )
            except:
                pass
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    # ============ ОТПРАВКА СООБЩЕНИЯ ============
    
    @bot.message_handler(commands=['send'])
    def cmd_send(message):
        """Отправить сообщение пользователю"""
        if not is_admin(message.from_user.id):
            return
        
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            bot.send_message(
                message.chat.id,
                "Использование: <code>/send ID ТЕКСТ</code>\n\n"
                "Пример: <code>/send 123456789 Привет!</code>",
                parse_mode="HTML"
            )
            return
        
        try:
            user_id = int(args[1])
            text_to_send = args[2]
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID должен быть числом")
            return
        
        try:
            bot.send_message(user_id, text_to_send, parse_mode="HTML")
            bot.send_message(
                message.chat.id,
                f"✅ <b>Сообщение отправлено!</b>\n\n"
                f"👤 Получатель: <code>{user_id}</code>\n"
                f"📨 Текст: {text_to_send[:100]}...",
                parse_mode="HTML"
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Не удалось отправить: {e}")
    
    # ============ РАССЫЛКА ============
    
    # Состояние для рассылки
    broadcast_state = {}
    
    @bot.message_handler(commands=['broadcast'])
    def cmd_broadcast(message):
        """Начать рассылку"""
        if not is_admin(message.from_user.id):
            return
        
        broadcast_state[message.from_user.id] = 'waiting_text'
        
        bot.send_message(
            message.chat.id,
            "📢 <b>Рассылка</b>\n\n"
            "Отправьте текст сообщения для всех пользователей.\n"
            "Поддерживается HTML-форматирование.\n\n"
            "Для отмены: /cancel",
            parse_mode="HTML"
        )
    
    @bot.message_handler(func=lambda m: broadcast_state.get(m.from_user.id) == 'waiting_text')
    def process_broadcast_text(message):
        """Обработка текста рассылки"""
        if message.text == '/cancel':
            del broadcast_state[message.from_user.id]
            bot.send_message(message.chat.id, "❌ Рассылка отменена")
            return
        
        broadcast_state[message.from_user.id] = {
            'status': 'confirm',
            'text': message.text
        }
        
        # Считаем пользователей
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total = cursor.fetchone()['count']
        cursor.close()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"📢 <b>Подтверждение рассылки</b>\n\n"
            f"👥 Получателей: {total}\n\n"
            f"<b>Текст:</b>\n{message.text[:500]}\n\n"
            f"Отправьте <code>ДА</code> для подтверждения\n"
            f"Или /cancel для отмены",
            parse_mode="HTML"
        )
    
    @bot.message_handler(func=lambda m: isinstance(broadcast_state.get(m.from_user.id), dict) and broadcast_state.get(m.from_user.id, {}).get('status') == 'confirm')
    def confirm_broadcast(message):
        """Подтверждение и отправка рассылки"""
        if message.text == '/cancel':
            del broadcast_state[message.from_user.id]
            bot.send_message(message.chat.id, "❌ Рассылка отменена")
            return
        
        if message.text.upper() != 'ДА':
            bot.send_message(
                message.chat.id,
                "Отправьте <code>ДА</code> для подтверждения или /cancel",
                parse_mode="HTML"
            )
            return
        
        broadcast_text = broadcast_state[message.from_user.id]['text']
        del broadcast_state[message.from_user.id]
        
        # Получаем всех пользователей
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        progress_msg = bot.send_message(
            message.chat.id,
            f"📤 Рассылка началась... 0/{len(users)}"
        )
        
        success = 0
        failed = 0
        
        for i, user in enumerate(users):
            user_id = user['id']
            try:
                bot.send_message(user_id, broadcast_text, parse_mode="HTML")
                success += 1
            except Exception:
                failed += 1
            
            # Обновляем прогресс каждые 50 сообщений
            if (i + 1) % 50 == 0:
                try:
                    bot.edit_message_text(
                        f"📤 Рассылка... {i + 1}/{len(users)}\n"
                        f"✅ Успешно: {success}\n"
                        f"❌ Ошибок: {failed}",
                        message.chat.id,
                        progress_msg.message_id
                    )
                except:
                    pass
            
            # Задержка чтобы не получить бан
            import time
            time.sleep(0.05)
        
        bot.edit_message_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📬 Отправлено: {success}\n"
            f"❌ Не доставлено: {failed}\n"
            f"📊 Всего: {len(users)}",
            message.chat.id,
            progress_msg.message_id,
            parse_mode="HTML"
        )
    
    # ============ ИНФОРМАЦИЯ О БД ============
    
    @bot.message_handler(commands=['dbinfo'])
    def cmd_dbinfo(message):
        """Информация о базе данных"""
        if not is_admin(message.from_user.id):
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Список таблиц
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            tables_info = ""
            for table in tables:
                table_name = list(table.values())[0]
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count = cursor.fetchone()['count']
                tables_info += f"  • {table_name}: {count} записей\n"
            
            cursor.close()
            conn.close()
            
            text = f"""🗄 <b>База данных</b>

<b>Таблицы:</b>
{tables_info}"""
            
            bot.send_message(message.chat.id, text, parse_mode="HTML")
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    # ============ ОТМЕНА ============
    
    @bot.message_handler(commands=['cancel'])
    def cmd_cancel(message):
        """Отмена текущего действия"""
        user_id = message.from_user.id
        
        if user_id in broadcast_state:
            del broadcast_state[user_id]
            bot.send_message(message.chat.id, "❌ Действие отменено")
        else:
            bot.send_message(message.chat.id, "Нечего отменять")

    # ============ ПРОМОКОДЫ ============
    
    @bot.message_handler(commands=['addpromo'])
    def cmd_addpromo(message):
        """Создать промокод"""
        if not is_admin(message.from_user.id):
            return
        
        from handlers.promo import promo_states
        promo_states[message.from_user.id] = 'admin_waiting_promo_data'
        
        bot.send_message(
            message.chat.id,
            (
                "🎁 <b>Создание промокода</b>\n\n"
                "<b>1. Бесплатные генерации:</b>\n"
                "<code>КОД КОЛИЧЕСТВО ЛИМИТ</code>\n"
                "Пример: <code>FREE10 10 100</code>\n"
                "(промокод FREE10 даёт 10 генераций, можно использовать 100 раз)\n\n"
                "<b>2. Скидка (спеццена):</b>\n"
                "<code>КОД ЦЕНА КОЛИЧЕСТВО ЛИМИТ</code>\n"
                "Пример: <code>SALE99 99 20 50</code>\n"
                "(промокод SALE99 даёт купить 20 генераций за 99₽, лимит 50 использований)\n\n"
                "Для отмены: /cancel"
            ),
            parse_mode='HTML'
        )
    
    @bot.message_handler(func=lambda m: (
        is_admin(m.from_user.id) 
        and promo_states.get(m.from_user.id) == 'admin_waiting_promo_data'
        and m.text 
        and not m.text.startswith('/')
    ))
    def process_addpromo(message):
        """Обработка создания промокода"""
        from handlers.promo import promo_states
        from utils.db_utils import create_promo_code
        
        user_id = message.from_user.id
        
        try:
            parts = message.text.strip().split()
            
            if len(parts) == 3:
                # Бесплатные генерации: CODE AMOUNT LIMIT
                code = parts[0].upper()
                amount = int(parts[1])
                limit = int(parts[2])
                
                result = create_promo_code(
                    code=code,
                    promo_type='free',
                    generations_amount=amount,
                    max_uses=limit
                )
                desc = f"🎁 Даёт генераций: {amount}"
                
            elif len(parts) == 4:
                # Скидка: CODE PRICE AMOUNT LIMIT
                code = parts[0].upper()
                price = int(parts[1])
                amount = int(parts[2])
                limit = int(parts[3])
                
                result = create_promo_code(
                    code=code,
                    promo_type='discount',
                    generations_amount=amount,
                    discount_price=price,
                    max_uses=limit
                )
                desc = f"🏷 Скидка: {amount} генераций за {price}₽"
                
            else:
                raise ValueError("Неверное количество аргументов")
            
            if result:
                bot.send_message(
                    message.chat.id,
                    (
                        f"✅ <b>Промокод создан!</b>\n\n"
                        f"🔑 Код: <code>{code}</code>\n"
                        f"{desc}\n"
                        f"👥 Лимит: {limit} использований"
                    ),
                    parse_mode='HTML'
                )
            else:
                bot.send_message(message.chat.id, "❌ Ошибка: такой код уже существует")
                
        except ValueError:
            bot.send_message(
                message.chat.id,
                (
                    "❌ <b>Ошибка формата!</b>\n\n"
                    "Бесплатные: <code>КОД КОЛИЧЕСТВО ЛИМИТ</code>\n"
                    "Скидка: <code>КОД ЦЕНА КОЛИЧЕСТВО ЛИМИТ</code>"
                ),
                parse_mode='HTML'
            )
            return
        
        if user_id in promo_states:
            del promo_states[user_id]
    
    @bot.message_handler(commands=['listpromo'])
    def cmd_listpromo(message):
        """Список промокодов"""
        if not is_admin(message.from_user.id):
            return
        
        from utils.db_utils import get_all_promo_codes
        
        promos = get_all_promo_codes()
        
        if not promos:
            bot.send_message(message.chat.id, "📭 Промокодов пока нет")
            return
        
        text = "🎁 <b>Промокоды:</b>\n\n"
        for p in promos:
            status = "✅" if p['is_active'] else "❌"
            if p['type'] == 'free':
                desc = f"{p['generations_amount']} генераций бесплатно"
            else:
                desc = f"{p['generations_amount']} генераций за {p['discount_price']}₽"
            
            text += (
                f"{status} <code>{p['code']}</code>\n"
                f"   └ {desc}, использован {p['current_uses']}/{p['max_uses']}\n"
            )
        
        bot.send_message(message.chat.id, text, parse_mode='HTML')
    
    @bot.message_handler(commands=['delpromo'])
    def cmd_delpromo(message):
        """Деактивировать промокод"""
        if not is_admin(message.from_user.id):
            return
        
        args = message.text.split()
        if len(args) < 2:
            bot.send_message(
                message.chat.id,
                "Использование: <code>/delpromo КОД</code>",
                parse_mode='HTML'
            )
            return
        
        code = args[1].upper()
        from utils.db_utils import deactivate_promo_code
        
        if deactivate_promo_code(code):
            bot.send_message(message.chat.id, f"✅ Промокод <code>{code}</code> деактивирован", parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "❌ Ошибка деактивации")

    # ============ SEGMIND КРЕДИТЫ ============
    
    @bot.message_handler(commands=['credits'])
    def cmd_credits(message):
        """Проверка кредитов Segmind"""
        if not is_admin(message.from_user.id):
            return
        
        from utils.segmind_service import get_credits, is_segmind_available
        
        if not is_segmind_available():
            bot.send_message(
                message.chat.id,
                "❌ Segmind API не настроен. Проверьте SEGMIND_API_TOKEN в .env",
                parse_mode="HTML"
            )
            return
        
        bot.send_message(message.chat.id, "⏳ Проверяю кредиты...")
        
        result = get_credits()
        
        if "error" in result:
            bot.send_message(
                message.chat.id,
                f"❌ Ошибка: {result['error']}",
                parse_mode="HTML"
            )
            return
        
        credits = result.get('credits', 0)
        free_credits = result.get('free-credits', 0)
        total = credits + free_credits
        
        text = f"""💳 <b>Кредиты Segmind</b>

💰 Платные кредиты: <b>{credits:.4f}</b>
🎁 Бесплатные кредиты: <b>{free_credits:.4f}</b>
📊 Всего: <b>{total:.4f}</b>"""
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(commands=['checksubs'])
    def cmd_check_subscribers(message):
        """Проверить, сколько людей реально подписаны (не заблокировали)"""
        if not is_admin(message.from_user.id):
            return

        # Оборачиваем логику в функцию для запуска в отдельном потоке
        def check_loop():
            import time
            from telebot.apihelper import ApiTelegramException
            from config.database import get_connection
            from utils.db_utils import update_block_status
            
            # Отправляем начальное сообщение
            try:
                status_msg = bot.send_message(message.chat.id, "🔄 Начинаю проверку активных подписчиков...")
            except:
                return

            # Получаем всех пользователей (создаем новое подключение внутри потока)
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users")
                users = cursor.fetchall()
                cursor.close()
                conn.close()
                
                all_ids = [u['id'] for u in users]
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка БД: {e}")
                return

            total = len(all_ids)
            active = 0
            blocked = 0
            
            for i, user_id in enumerate(all_ids):
                try:
                    # send_chat_action - легкий способ проверить доступность ЛС
                    # Бот показывает "печатает...", если пользователь его не заблочил
                    bot.send_chat_action(chat_id=user_id, action="typing")
                    active += 1
                    
                    # Разблокируем в БД, если был блок
                    try:
                        update_block_status(user_id, 0)
                    except:
                        pass
                    
                except ApiTelegramException as e:
                    # 403 Forbidden - бот заблокирован
                    if "403" in str(e) or "Forbidden" in str(e):
                        blocked += 1
                        try:
                            update_block_status(user_id, 1)
                        except:
                            pass
                    else:
                        # Чат не найден и т.д.
                        blocked += 1
                except Exception:
                    blocked += 1

                # Обновляем статус каждые 50 пользователей
                if i > 0 and i % 50 == 0:
                    try:
                        bot.edit_message_text(
                            f"🔄 Проверено: {i}/{total}\n"
                            f"✅ Живых: {active}\n"
                            f"🚫 Блок: {blocked}",
                            message.chat.id,
                            status_msg.message_id
                        )
                    except:
                        pass
                
                # Небольшая задержка, чтобы не превысить лимиты Телеграм
                time.sleep(0.035)

            # Финальный отчет
            try:
                bot.edit_message_text(
                    f"📊 <b>Результат проверки:</b>\n\n"
                    f"👥 Всего в базе: {total}\n"
                    f"✅ <b>Активны: {active}</b> ({(active/total*100) if total else 0:.1f}%)\n"
                    f"🚫 Заблокировали: {blocked} ({(blocked/total*100) if total else 0:.1f}%)",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode="HTML"
                )
            except:
                pass

        # ЗАПУСК В ФОНЕ (Асинхронно относительно основного процесса)
        import threading
        threading.Thread(target=check_loop).start()


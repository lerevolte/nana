import asyncio
import logging
from utils.db_utils import get_pending_payments, update_payment_status, increase_balance, get_balance
from utils.yookassa_service import check_payment
from utils.yandex_api import metrica
from utils.task_processor import task_processor_loop

logger = logging.getLogger(__name__)

def plural_generations(n):
    """Склонение слова 'генерация'"""
    if n is None:
        n = 0
    n = abs(int(n))
    
    if n % 10 == 1 and n % 100 != 11:
        return "генерация"
    elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return "генерации"
    else:
        return "генераций"

async def check_payments_loop(bot):
    """Фоновая проверка платежей"""
    logger.info("Starting payment checker...")
    
    while True:
        try:
            payments = get_pending_payments()
            
            for payment in payments:
                payment_id = payment["payment_id"]
                user_id = payment["user_id"]
                generations_count = payment["generations"]
                
                # Проверяем статус в ЮKassa
                result = check_payment(payment_id)
                
                if result["status"] == "succeeded":
                    amount_val = result.get('amount', '0')
                    
                    # Начисляем генерации
                    new_balance = increase_balance(user_id, generations_count)

                    try:
                        revenue = float(amount_val)

                        logger.info(f"💰 Пытаюсь отправить конверсию в Метрику:")
                        logger.info(f"   client_id={user_id}, goal=payment, price={revenue}")
                        
                        from config import YANDEX_OAUTH_TOKEN, YANDEX_METRICA_ID
                        logger.info(f"   YANDEX_OAUTH_TOKEN exists: {bool(YANDEX_OAUTH_TOKEN)}")
                        logger.info(f"   YANDEX_METRICA_ID: {YANDEX_METRICA_ID}")
                        
                        await metrica.upload_conversion(
                            client_id=str(user_id),
                            goal_name="payment",
                            user_id=user_id
                        )

                        
                        logger.info(f"Отправляем конверсию в Метрику")
                        
                    except Exception as e:
                        logger.error(f"⚠️ Ошибка отправки конверсии в Метрику: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

                    
                    # Обновляем статус
                    update_payment_status(payment_id, "succeeded")

                    logger.info(f"Payment {payment_id} succeeded, {generations_count} generations added to user {user_id}")
                    
                    # Уведомляем пользователя
                    try:
                        from keyboards.reply import get_main_menu_keyboard
                        
                        bot.send_message(
                            user_id,
                            f"✅ <b>Оплата подтверждена!</b>\n\n"
                            f"🎨 Начислено: {generations_count} {plural_generations(generations_count)}\n"
                            f"💎 Ваш баланс: {new_balance} {plural_generations(new_balance)}\n\n"
                            f"Теперь можете создавать изображения!\n\n",
                            reply_markup=get_main_menu_keyboard(),
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user {user_id}: {e}")
                    
                    # Уведомляем админов о платеже
                    from utils.notifications import notify_payment
                    notify_payment(
                        bot,
                        user_id=user_id,
                        amount=amount_val,
                        generations_count=generations_count
                    )

                    from utils.db_utils import mark_user_as_paid, check_and_reward_referrer
                    
                    mark_user_as_paid(user_id)
                    
                    REFERRAL_REWARD = 5  # Генераций за оплатившего друга
                    referrer_id = check_and_reward_referrer(user_id, REFERRAL_REWARD)
                    
                    if referrer_id:
                        try:
                            bot.send_message(
                                referrer_id,
                                (
                                    f"🎉 <b>Ваш друг оплатил!</b>\n\n"
                                    f"Вам начислено <b>{REFERRAL_REWARD} генераций</b> "
                                    f"за приглашённого друга!"
                                ),
                                parse_mode='HTML'
                            )
                        except:
                            pass
                
                elif result["status"] == "canceled":
                    update_payment_status(payment_id, "canceled")
                    
                    try:
                        bot.send_message(
                            user_id,
                            "❌ <b>Платёж отменён</b>\n\n"
                            "Попробуйте ещё раз или выберите другой способ оплаты.",
                            parse_mode='HTML'
                        )
                    except:
                        pass
                    
                    logger.info(f"Payment {payment_id} canceled")
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in check_payments_loop: {e}")
        
        # Проверяем каждые 30 секунд
        await asyncio.sleep(30)

def start_background_tasks(bot):
    """Запуск фоновых задач"""
    import threading
    
    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Запускаем обе задачи параллельно
        loop.create_task(check_payments_loop(bot))
        loop.create_task(cleanup_images_loop())
        loop.create_task(task_processor_loop(bot))
        #loop.create_task(cleanup_states_loop())
        
        loop.run_forever()
    
    thread = threading.Thread(target=run_async_loop, daemon=True)
    thread.start()
    logger.info("Background tasks started")


async def cleanup_images_loop():
    """Периодическая очистка старых изображений"""
    while True:
        try:
            from utils.image_hosting import cleanup_old_images
            cleanup_old_images(max_age_seconds=1800)  # 30 минут
        except Exception as e:
            logger.error(f"Image cleanup error: {e}")
        
        await asyncio.sleep(600)  # Каждые 10 минут
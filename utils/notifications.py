import logging
from config.database import get_connection

logger = logging.getLogger(__name__)


def get_admin_ids():
    """Получает список ID админов из .env"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    return [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]


def notify_admins(bot, message: str, parse_mode: str = "HTML"):
    """
    Отправляет уведомление всем админам.
    """
    admin_ids = get_admin_ids()
    
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, message, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


def notify_new_user(bot, user_id: int, username: str, first_name: str, referrer_id: int = None, utms: dict = None):
    """Уведомление о новом пользователе"""
    ref_text = f"\n🔗 Реферер: {referrer_id}" if referrer_id else ""
    
    utm_text = ""
    if utms:
        utm_text += "\n📊 <b>Метки рекламы:</b>"
        if utms.get("utm_source"): utm_text += f"\n• Source: {utms['utm_source']}"
        if utms.get("utm_medium"): utm_text += f"\n• Medium: {utms['utm_medium']}"
        if utms.get("utm_campaign"): utm_text += f"\n• Campaign: {utms['utm_campaign']}"
        if utms.get("utm_content"): utm_text += f"\n• Content: {utms['utm_content']}"
        if utms.get("utm_term"): utm_text += f"\n• Term: {utms['utm_term']}"
    
    notify_admins(
        bot,
        f"👤 <b>Новый пользователь!</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {first_name}\n"
        f"📛 Username: @{username or 'нет'}"
        f"{ref_text}"
        f"{utm_text}"
    )


def notify_payment(bot, user_id: int, amount: str, generations_count: int, payment_type: str = "ЮKassa"):
    """Уведомление об оплате с датой регистрации по МСК"""
    from datetime import datetime, timedelta
    
    # Получаем данные пользователя для даты регистрации
    reg_date_str = "Неизвестно"
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT created_at FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and user.get("created_at"):
            raw_date = user["created_at"]
            
            if isinstance(raw_date, datetime):
                dt = raw_date
            else:
                dt = datetime.strptime(str(raw_date).split('.')[0], "%Y-%m-%d %H:%M:%S")
            
            # Время в БД в UTC — добавляем 3 часа для МСК
            dt_msk = dt + timedelta(hours=3)
            reg_date_str = dt_msk.strftime("%d.%m.%Y %H:%M")
            
    except Exception as e:
        logger.error(f"Error getting user date for {user_id}: {e}")
    
    notify_admins(
        bot,
        f"💰 <b>Новая оплата!</b>\n\n"
        f"📅 Подписка (МСК): {reg_date_str}\n"
        f"🆔 Пользователь: <code>{user_id}</code>\n"
        f"💵 Сумма: {amount}₽\n"
        f"🎨 Генераций: {generations_count}\n"
        f"💳 Способ: {payment_type}"
    )


def notify_error(bot, error_type: str, error_message: str, user_id: int = None):
    """Уведомление об ошибке"""
    user_text = f"\n🆔 Пользователь: <code>{user_id}</code>" if user_id else ""
    
    notify_admins(
        bot,
        f"❌ <b>Ошибка: {error_type}</b>\n"
        f"{user_text}\n"
        f"📝 {error_message}"
    )


def notify_promo_used(bot, user_id: int, code: str, generations: int):
    """Уведомление об использовании промокода"""
    notify_admins(
        bot,
        f"🎁 <b>Промокод использован!</b>\n\n"
        f"🆔 Пользователь: <code>{user_id}</code>\n"
        f"🏷 Код: {code}\n"
        f"🎨 Начислено: {generations} генераций"
    )
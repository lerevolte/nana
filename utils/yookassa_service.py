import uuid
import re
import logging
from yookassa import Configuration, Payment
import os

logger = logging.getLogger(__name__)

# Инициализация ЮKassa
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
YOOKASSA_RETURN_URL = os.getenv('YOOKASSA_RETURN_URL', 'https://t.me/your_bot_username')

if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY

PRICES = {
    7: 150,
    50: 450,
    100: 850,
    150: 1230,
    200: 1600,
    250: 1950,
    300: 2280
}

def normalize_phone(phone: str) -> str | None:
    """
    Приводит телефон к формату 7XXXXXXXXXX для Юкассы.
    Возвращает None если номер невалидный.
    """
    if not phone:
        return None
    
    # Убираем всё кроме цифр
    digits = ''.join(filter(str.isdigit, phone))
    
    # Приводим к формату 7XXXXXXXXXX
    if len(digits) == 11:
        if digits.startswith('8'):
            digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    
    # Проверяем итоговую длину и формат
    if len(digits) != 11 or not digits.startswith('7'):
        return None
    
    return digits

def validate_email(email: str) -> bool:
    """Проверяет валидность email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def create_payment(user_id: int, generations_count: int, user_contact: str = None, custom_price: int = None) -> dict:
    """
    Создаёт платёж в ЮKassa
    user_contact: Email или телефон от пользователя.
    """
    logger.info(f"Creating payment for user {user_id}, contact: {user_contact}")

    from utils.closing import PAYMENTS_DISABLED
    if PAYMENTS_DISABLED:
        return {"success": False, "error": "Покупка генераций больше недоступна"}

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        return {"success": False, "error": "ЮKassa не настроена"}
    
    price = PRICES.get(generations_count)
    if custom_price is not None:
        price = custom_price

    if not price:
        return {"success": False, "error": f"Неверное количество генераций: {generations_count}"}
    
    try:
        idempotence_key = str(uuid.uuid4())
        
        # Формирование данных клиента
        customer_data = {}
        
        if not user_contact:
            customer_data = {"email": "customer@imagebot.com"}
        else:
            user_contact = str(user_contact).strip()
            
            # Проверяем Email
            if '@' in user_contact and validate_email(user_contact):
                customer_data['email'] = user_contact
            # Проверяем телефон
            else:
                phone = normalize_phone(user_contact)
                if phone:
                    customer_data['phone'] = phone
                else:
                    # Контакт невалидный
                    return {
                        "success": False, 
                        "error": "invalid_contact",
                        "message": "Некорректный Email или телефон. Телефон должен быть в формате +79XXXXXXXXX"
                    }

        if not customer_data:
            customer_data = {"email": "customer@imagebot.com"}
             
        logger.info(f"Customer data: {customer_data}")

        payment = Payment.create({
            "amount": {
                "value": str(price) + ".00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": f"Покупка {generations_count} генераций изображений",
            "metadata": {
                "user_id": str(user_id),
                "generations_count": str(generations_count)
            },
            "receipt": {
                "customer": customer_data,
                "items": [
                    {
                        "description": f"Генерация {generations_count} изображений",
                        "quantity": "1.00",
                        "amount": {
                            "value": str(price) + ".00",
                            "currency": "RUB"
                        },
                        "vat_code": 1,  # НДС 20%
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            }
        }, idempotence_key)
        
        return {
            "success": True,
            "payment_url": payment.confirmation.confirmation_url,
            "payment_id": payment.id
        }
        
    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def check_payment(payment_id: str) -> dict:
    """Проверяет статус платежа"""
    try:
        payment = Payment.find_one(payment_id)
        
        return {
            "status": payment.status,
            "user_id": int(payment.metadata.get("user_id", 0)),
            "generations_count": int(payment.metadata.get("generations_count", 0)),
            "amount": payment.amount.value
        }
        
    except Exception as e:
        logger.error(f"Payment check error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
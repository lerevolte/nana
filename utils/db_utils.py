from config.database import get_connection
from utils.closing import FREE_CREDITS_DISABLED
import hashlib
import time
from typing import Optional

def get_or_create_user(user_id, username, first_name, utm_source=None, utm_medium=None, 
                       utm_campaign=None, utm_content=None, utm_term=None, ym_client_id=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            # Новый пользователь — сохраняем UTM-метки
            cursor.execute(
                '''INSERT INTO users (id, username, first_name, generations_balance, has_received_welcome_bonus,
                   selected_aspect_ratio, utm_source, utm_medium, utm_campaign, utm_content, utm_term, ym_client_id) 
                   VALUES (%s, %s, %s, %s, TRUE, '1:1', %s, %s, %s, %s, %s, %s)''',
                (user_id, username, first_name, 0 if FREE_CREDITS_DISABLED else 1, utm_source, utm_medium, utm_campaign, utm_content, utm_term, ym_client_id)
            )
            conn.commit()
            
            user = {
                'id': user_id,
                'username': username,
                'first_name': first_name,
                'generations_balance': 0 if FREE_CREDITS_DISABLED else 1,
                'selected_model': 'google/nano-banana',
                'selected_aspect_ratio': '1:1',
                'has_received_welcome_bonus': True,
                'is_new': True,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'utm_content': utm_content,
                'utm_term': utm_term,
                'ym_client_id': ym_client_id
            }
        else:
            user['is_new'] = False
        
        cursor.close()
        conn.close()
        return user
        
    except Exception as e:
        print(f'Ошибка при работе с БД: {e}')
        raise e

def update_user_aspect_ratio(user_id, aspect_ratio):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET selected_aspect_ratio = %s WHERE id = %s', (aspect_ratio, user_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Ошибка при обновлении формата: {e}')

def get_user_model(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT selected_model, selected_aspect_ratio FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            model = result['selected_model'] or 'google/nano-banana'
            aspect_ratio = result['selected_aspect_ratio'] or '1:1'
            
            # Если формат match_input_image — меняем на 1:1 для генерации
            if aspect_ratio == 'match_input_image':
                aspect_ratio = '1:1'
            
            return model, aspect_ratio
        
        return 'google/nano-banana', '1:1'
    except Exception as e:
        print(f'Ошибка при получении модели: {e}')
        return 'google/nano-banana', '1:1'

async def get_user(user_id: int) -> Optional[dict]:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return result
        
        return None
    except Exception as e:
        print(f'Ошибка при получении  пользователя: {e}')
        return None

def decrease_balance(user_id, amount=1):
    """Уменьшает баланс на указанное количество генераций"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET generations_balance = generations_balance - %s WHERE id = %s', 
            (amount, user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Ошибка при уменьшении баланса: {e}')

def get_balance(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT generations_balance FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['generations_balance'] if result else 0
    except Exception as e:
        print(f'Ошибка при получении баланса: {e}')
        return 0

def update_user_model(user_id, model):
    """Обновляет выбранную модель пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET selected_model = %s WHERE id = %s', (model, user_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Ошибка при обновлении модели: {e}')

def increase_balance(user_id, amount):
    """Увеличивает баланс генераций пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET generations_balance = generations_balance + %s WHERE id = %s',
            (amount, user_id)
        )
        conn.commit()
        # Получаем новый баланс
        cursor.execute('SELECT generations_balance FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result['generations_balance'] if result else 0
    except Exception as e:
        print(f'Ошибка при увеличении баланса: {e}')
        return 0

def create_payment(user_id, payment_id, amount, generations):
    """Создаёт запись о платеже"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO payments (user_id, payment_id, amount, generations, status)
               VALUES (%s, %s, %s, %s, 'pending')''',
            (user_id, payment_id, amount, generations)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Ошибка при создании платежа: {e}')

def update_payment_status(payment_id, status):
    """Обновляет статус платежа"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE payments SET status = %s WHERE payment_id = %s',
            (status, payment_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Ошибка при обновлении статуса: {e}')

def get_payment_by_id(payment_id):
    """Получает информацию о платеже"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM payments WHERE payment_id = %s', (payment_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f'Ошибка при получении платежа: {e}')
        return None

def update_user_contact(user_id, contact):
    """Обновляет контакт пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET contact = %s WHERE id = %s', (contact, user_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f'Ошибка при обновлении контакта: {e}')

def get_pending_payments():
    """Получает все ожидающие платежи"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE status = 'pending'")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f'Ошибка при получении платежей: {e}')
        return []

def generate_referral_code(user_id):
    """Генерирует уникальный реферальный код"""
    hash_input = f"{user_id}{time.time()}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:8].upper()

def get_or_set_referral_code(user_id):
    """Получает или создаёт реферальный код"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT referral_code FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        
        if result and result['referral_code']:
            code = result['referral_code']
        else:
            # Генерируем новый код
            code = generate_referral_code(user_id)
            cursor.execute('UPDATE users SET referral_code = %s WHERE id = %s', (code, user_id))
            conn.commit()
        
        cursor.close()
        conn.close()
        return code
    except Exception as e:
        print(f'Ошибка при получении реферального кода: {e}')
        return None

def add_referral(referrer_id, referred_id):
    """Добавляет реферала и начисляет бонус"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Проверяем, не был ли уже добавлен этот реферал
        cursor.execute(
            'SELECT * FROM referrals WHERE referrer_id = %s AND referred_id = %s',
            (referrer_id, referred_id)
        )
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False
        
        # Добавляем реферала
        cursor.execute(
            'INSERT INTO referrals (referrer_id, referred_id, rewarded) VALUES (%s, %s, TRUE)',
            (referrer_id, referred_id)
        )
        
        # Обновляем referred_by у приглашённого
        cursor.execute('UPDATE users SET referred_by = %s WHERE id = %s', (referrer_id, referred_id))
        
        if not FREE_CREDITS_DISABLED:
            cursor.execute(
                'UPDATE users SET generations_balance = generations_balance + 3 WHERE id = %s',
                (referrer_id,)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f'Ошибка при добавлении реферала: {e}')
        return False

def get_user_by_referral_code(referral_code):
    """Находит пользователя по реферальному коду"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE referral_code = %s', (referral_code,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['id'] if result else None
    except Exception as e:
        print(f'Ошибка при поиске по реферальному коду: {e}')
        return None

def get_referral_stats(user_id):
    """Получает статистику по рефералам"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) as count FROM referrals WHERE referrer_id = %s',
            (user_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['count'] if result else 0
    except Exception as e:
        print(f'Ошибка при получении статистики рефералов: {e}')
        return 0

def check_and_add_daily_generation(user_id):
    """Проверяет и добавляет ежедневную генерацию если нужно (по московскому времени)"""
    try:
        from config.database import get_moscow_date
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Получаем дату последнего начисления
        cursor.execute(
            'SELECT last_free_generation_date FROM users WHERE id = %s',
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return False
        
        today = get_moscow_date()
        last_date = result['last_free_generation_date']
        
        # Если последнее начисление было не сегодня (по московскому времени)
        if last_date is None or last_date < today:
            cursor.execute(
                'UPDATE users SET generations_balance = generations_balance + 1, last_free_generation_date = %s WHERE id = %s',
                (today, user_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return True
        
        cursor.close()
        conn.close()
        return False
    except Exception as e:
        print(f'Ошибка при начислении ежедневной генерации: {e}')
        return False

# ============ ПРОМОКОДЫ ============

def create_promo_code(code, promo_type='free', generations_amount=0, discount_price=None, max_uses=100):
    """Создаёт промокод"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''INSERT INTO promo_codes (code, type, generations_amount, discount_price, max_uses)
               VALUES (%s, %s, %s, %s, %s)''',
            (code.upper(), promo_type, generations_amount, discount_price, max_uses)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f'Ошибка создания промокода: {e}')
        return False


def get_promo_code(code):
    """Получает информацию о промокоде"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM promo_codes WHERE code = %s AND is_active = TRUE',
            (code.upper(),)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f'Ошибка получения промокода: {e}')
        return None


def use_promo_code(user_id, code):
    """Использует промокод для пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Проверяем, не использовал ли уже
        cursor.execute(
            'SELECT * FROM promo_uses WHERE user_id = %s AND promo_code = %s',
            (user_id, code.upper())
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'already_used'}
        
        # Получаем промокод
        cursor.execute(
            'SELECT * FROM promo_codes WHERE code = %s AND is_active = TRUE',
            (code.upper(),)
        )
        promo = cursor.fetchone()
        
        if not promo or (FREE_CREDITS_DISABLED and promo['type'] == 'free'):
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'not_found'}
        
        if promo['current_uses'] >= promo['max_uses']:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'limit_reached'}
        
        # Записываем использование
        cursor.execute(
            'INSERT INTO promo_uses (user_id, promo_code) VALUES (%s, %s)',
            (user_id, code.upper())
        )
        
        # Увеличиваем счётчик использований
        cursor.execute(
            'UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = %s',
            (code.upper(),)
        )
        
        # Если бесплатные генерации — начисляем сразу
        if promo['type'] == 'free':
            cursor.execute(
                'UPDATE users SET generations_balance = generations_balance + %s WHERE id = %s',
                (promo['generations_amount'], user_id)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'type': promo['type'],
            'generations_amount': promo['generations_amount'],
            'discount_price': promo['discount_price']
        }
    except Exception as e:
        print(f'Ошибка использования промокода: {e}')
        return {'success': False, 'error': str(e)}


def get_all_promo_codes(limit=20):
    """Получает список всех промокодов"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM promo_codes ORDER BY created_at DESC LIMIT %s',
            (limit,)
        )
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f'Ошибка получения промокодов: {e}')
        return []


def deactivate_promo_code(code):
    """Деактивирует промокод"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE promo_codes SET is_active = FALSE WHERE code = %s',
            (code.upper(),)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f'Ошибка деактивации промокода: {e}')
        return False


# ============ РЕФЕРАЛЬНАЯ СИСТЕМА С ОПЛАТОЙ ============

def mark_user_as_paid(user_id):
    """Отмечает, что пользователь совершил оплату"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Отмечаем пользователя как оплатившего
        cursor.execute(
            'UPDATE users SET has_paid = TRUE WHERE id = %s',
            (user_id,)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f'Ошибка отметки оплаты: {e}')
        return False


def check_and_reward_referrer(user_id, reward_generations=5):
    """Проверяет и награждает реферера после оплаты пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Находим реферала, который привёл этого пользователя и ещё не получил награду
        cursor.execute(
            '''SELECT r.referrer_id FROM referrals r
               WHERE r.referred_id = %s AND r.paid_reward = FALSE''',
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return None
        
        referrer_id = result['referrer_id']
        
        if FREE_CREDITS_DISABLED:
            cursor.close()
            conn.close()
            return None
        
        cursor.execute(
            'UPDATE users SET generations_balance = generations_balance + %s WHERE id = %s',
            (reward_generations, referrer_id)
        )
        
        # Отмечаем, что награда выдана
        cursor.execute(
            'UPDATE referrals SET paid_reward = TRUE WHERE referred_id = %s',
            (user_id,)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return referrer_id
    except Exception as e:
        print(f'Ошибка награждения реферера: {e}')
        return None


def get_referral_stats_detailed(user_id):
    """Получает детальную статистику по рефералам"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Всего приглашено
        cursor.execute(
            'SELECT COUNT(*) as total FROM referrals WHERE referrer_id = %s',
            (user_id,)
        )
        total = cursor.fetchone()['total']
        
        # Оплативших (за которых получена награда)
        cursor.execute(
            'SELECT COUNT(*) as paid FROM referrals WHERE referrer_id = %s AND paid_reward = TRUE',
            (user_id,)
        )
        paid = cursor.fetchone()['paid']
        
        cursor.close()
        conn.close()
        
        return {
            'total': total,
            'paid': paid,
            'pending': total - paid
        }
    except Exception as e:
        print(f'Ошибка получения статистики рефералов: {e}')
        return {'total': 0, 'paid': 0, 'pending': 0}

async def update_block_status(user_id: int, is_blocked: int):
    """Обновить статус блокировки"""
    conn = get_connection()
    async with conn.cursor() as cursor:
        await cursor.execute(
            "UPDATE users SET is_blocked = %s WHERE user_id = %s",
            (is_blocked, user_id)
        )

"""
Менеджер состояний пользователей с сохранением в БД.
Позволяет сохранять состояния между перезапусками бота.
"""

import json
import logging
from config.database import get_connection
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Кэш состояний в памяти для быстрого доступа
_states_cache = {}


def get_user_state(user_id: int) -> dict | None:
    """
    Получает состояние пользователя.
    Сначала проверяет кэш, потом БД.
    """
    # Проверяем кэш
    if user_id in _states_cache:
        return _states_cache[user_id]
    
    # Загружаем из БД
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT state_type, state_data FROM user_states WHERE user_id = %s',
            (user_id,)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            state = {
                'type': result['state_type'],
                'data': json.loads(result['state_data']) if result['state_data'] else {}
            }
            _states_cache[user_id] = state
            return state
        
        return None
        
    except Exception as e:
        logger.error(f'[StateManager] Error getting state for {user_id}: {e}')
        return None


def set_user_state(user_id: int, state_type: str, state_data: dict = None):
    """
    Устанавливает состояние пользователя.
    Сохраняет в кэш и в БД.
    """
    state = {
        'type': state_type,
        'data': state_data or {}
    }
    
    # Сохраняем в кэш
    _states_cache[user_id] = state
    
    # Сохраняем в БД
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_states (user_id, state_type, state_data)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                state_type = VALUES(state_type),
                state_data = VALUES(state_data),
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, state_type, json.dumps(state_data or {})))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f'[StateManager] Error saving state for {user_id}: {e}')


def clear_user_state(user_id: int):
    """Очищает состояние пользователя"""
    # Удаляем из кэша
    if user_id in _states_cache:
        del _states_cache[user_id]
    
    # Удаляем из БД
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM user_states WHERE user_id = %s', (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f'[StateManager] Error clearing state for {user_id}: {e}')


def get_state_type(user_id: int) -> str | None:
    """Возвращает только тип состояния (для совместимости)"""
    state = get_user_state(user_id)
    return state['type'] if state else None


def get_state_data(user_id: int, key: str = None):
    """Возвращает данные состояния или конкретный ключ"""
    state = get_user_state(user_id)
    if not state:
        return None
    
    if key:
        return state['data'].get(key)
    return state['data']


def update_state_data(user_id: int, key: str, value):
    """Обновляет конкретное поле в данных состояния"""
    state = get_user_state(user_id)
    if not state:
        return
    
    state['data'][key] = value
    set_user_state(user_id, state['type'], state['data'])


def cleanup_old_states(hours: int = 24):
    """Удаляет старые состояния (старше указанного количества часов)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM user_states 
            WHERE updated_at < DATE_SUB(NOW(), INTERVAL %s HOUR)
        ''', (hours,))
        
        deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if deleted > 0:
            logger.info(f'[StateManager] Cleaned up {deleted} old states')
        
    except Exception as e:
        logger.error(f'[StateManager] Error cleaning up states: {e}')


# ============ Совместимость со старым API ============

class StateDict:
    """
    Класс-обёртка для совместимости с dict-подобным API.
    Позволяет использовать как: user_states[user_id] = 'waiting_for_prompt'
    """
    
    def __init__(self, state_prefix: str):
        self.prefix = state_prefix
    
    def _make_type(self, value):
        """Формирует полный тип состояния"""
        if isinstance(value, str):
            return f"{self.prefix}:{value}"
        return f"{self.prefix}:active"
    
    def _parse_type(self, full_type: str) -> str | None:
        """Извлекает значение из полного типа"""
        if full_type and full_type.startswith(f"{self.prefix}:"):
            return full_type.replace(f"{self.prefix}:", "")
        return None
    
    def get(self, user_id: int, default=None):
        """Получает состояние пользователя"""
        state = get_user_state(user_id)
        if state and state['type'].startswith(f"{self.prefix}:"):
            return self._parse_type(state['type'])
        return default
    
    def __getitem__(self, user_id: int):
        return self.get(user_id)
    
    def __setitem__(self, user_id: int, value):
        set_user_state(user_id, self._make_type(value), {})
    
    def __delitem__(self, user_id: int):
        state = get_user_state(user_id)
        if state and state['type'].startswith(f"{self.prefix}:"):
            clear_user_state(user_id)
    
    def __contains__(self, user_id: int):
        return self.get(user_id) is not None
    
    def pop(self, user_id: int, default=None):
        value = self.get(user_id, default)
        if user_id in self:
            del self[user_id]
        return value


class StateDataDict:
    """
    Класс для хранения данных вместе с состоянием.
    Например, для хранения file_id изображения.
    """
    
    def __init__(self, data_key: str):
        self.data_key = data_key
    
    def get(self, user_id: int, default=None):
        return get_state_data(user_id, self.data_key) or default
    
    def __getitem__(self, user_id: int):
        return self.get(user_id)
    
    def __setitem__(self, user_id: int, value):
        update_state_data(user_id, self.data_key, value)
    
    def __delitem__(self, user_id: int):
        state = get_user_state(user_id)
        if state and self.data_key in state['data']:
            del state['data'][self.data_key]
            set_user_state(user_id, state['type'], state['data'])
    
    def __contains__(self, user_id: int):
        return self.get(user_id) is not None
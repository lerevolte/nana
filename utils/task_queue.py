"""
Очередь задач генерации с сохранением в БД.
Позволяет восстанавливать задачи после перезапуска бота.
"""

import json
import logging
from config.database import get_connection
from datetime import datetime

logger = logging.getLogger(__name__)


def create_task(
    user_id: int,
    chat_id: int,
    task_type: str,
    model: str = None,
    prompt: str = None,
    aspect_ratio: str = None,
    style: str = None,
    cost: int = 1,
    image_file_id: str = None,
    image2_file_id: str = None,
    extra_data: dict = None
) -> int:
    """
    Создаёт задачу в очереди.
    Возвращает ID задачи.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO generation_queue 
            (user_id, chat_id, task_type, model, prompt, aspect_ratio, style, cost, 
             image_file_id, image2_file_id, extra_data, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        ''', (
            user_id, chat_id, task_type, model, prompt, aspect_ratio, style, cost,
            image_file_id, image2_file_id, 
            json.dumps(extra_data) if extra_data else None
        ))
        
        task_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"[TaskQueue] Created task {task_id} for user {user_id}: {task_type}")
        return task_id
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error creating task: {e}")
        raise


def get_pending_tasks(limit: int = 10) -> list:
    """Получает задачи со статусом pending"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM generation_queue 
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT %s
        ''', (limit,))
        
        tasks = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return tasks
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error getting pending tasks: {e}")
        return []


def get_processing_tasks() -> list:
    """Получает задачи со статусом processing (прерванные)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM generation_queue 
            WHERE status = 'processing'
            ORDER BY created_at ASC
        ''')
        
        tasks = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return tasks
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error getting processing tasks: {e}")
        return []


def mark_task_processing(task_id: int):
    """Помечает задачу как выполняющуюся"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE generation_queue 
            SET status = 'processing', started_at = NOW()
            WHERE id = %s
        ''', (task_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error marking task {task_id} as processing: {e}")


def mark_task_completed(task_id: int, result_file_id: str = None):
    """Помечает задачу как выполненную"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE generation_queue 
            SET status = 'completed', completed_at = NOW(), result_file_id = %s
            WHERE id = %s
        ''', (result_file_id, task_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"[TaskQueue] Task {task_id} completed")
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error marking task {task_id} as completed: {e}")


def mark_task_failed(task_id: int, error_message: str):
    """Помечает задачу как проваленную"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE generation_queue 
            SET status = 'failed', completed_at = NOW(), error_message = %s
            WHERE id = %s
        ''', (error_message, task_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"[TaskQueue] Task {task_id} failed: {error_message}")
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error marking task {task_id} as failed: {e}")


def reset_processing_to_pending():
    """
    Сбрасывает все processing задачи обратно в pending.
    Вызывается при старте бота для восстановления прерванных задач.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE generation_queue 
            SET status = 'pending', started_at = NULL
            WHERE status = 'processing'
        ''')
        
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if affected > 0:
            logger.info(f"[TaskQueue] Reset {affected} interrupted tasks to pending")
        
        return affected
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error resetting tasks: {e}")
        return 0


def cleanup_old_tasks(days: int = 7):
    """Удаляет старые завершённые/проваленные задачи"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM generation_queue 
            WHERE status IN ('completed', 'failed')
            AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
        ''', (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if deleted > 0:
            logger.info(f"[TaskQueue] Cleaned up {deleted} old tasks")
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error cleaning up tasks: {e}")


def get_task_by_id(task_id: int) -> dict:
    """Получает задачу по ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM generation_queue WHERE id = %s', (task_id,))
        task = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return task
        
    except Exception as e:
        logger.error(f"[TaskQueue] Error getting task {task_id}: {e}")
        return None
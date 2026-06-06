import asyncio
import logging
from datetime import datetime, time
from config.database import get_moscow_time, get_moscow_date, get_connection

logger = logging.getLogger(__name__)

async def daily_generation_task():
    """Фоновая задача для начисления ежедневных генераций в 00:00 по Москве"""
    logger.info("Daily generation scheduler started")
    
    last_processed_date = None
    
    while True:
        try:
            moscow_now = get_moscow_time()
            current_date = moscow_now.date()
            current_hour = moscow_now.hour
            current_minute = moscow_now.minute
            
            # Проверяем, что сейчас 00:00-00:05 и мы ещё не обрабатывали этот день
            if current_hour == 0 and current_minute < 5 and last_processed_date != current_date:
                logger.info(f"Running daily generation task for {current_date}")
                
                # Начисляем генерации всем пользователям
                conn = get_connection()
                cursor = conn.cursor()
                
                # Обновляем всех пользователей, у которых last_free_generation_date < сегодня
                cursor.execute(
                    '''UPDATE users 
                       SET generations_balance = generations_balance + 1,
                           last_free_generation_date = %s
                       WHERE last_free_generation_date < %s OR last_free_generation_date IS NULL''',
                    (current_date, current_date)
                )
                
                affected = cursor.rowcount
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.info(f"Daily generations added to {affected} users")
                last_processed_date = current_date
            
        except Exception as e:
            logger.error(f"Error in daily_generation_task: {e}")
        
        # Проверяем каждую минуту
        await asyncio.sleep(60)
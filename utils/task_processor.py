"""
Обработчик задач генерации.
Выполняет задачи из очереди и отправляет результаты пользователям.
"""

import asyncio
import logging
from io import BytesIO

from utils.task_queue import (
    get_pending_tasks, mark_task_processing, mark_task_completed, 
    mark_task_failed, reset_processing_to_pending
)
from utils.db_utils import get_balance, decrease_balance
from utils.constants import BOT_SIGNATURE
from utils.image_hosting import upload_image  # <--- Добавлен импорт

logger = logging.getLogger(__name__)


async def process_task(bot, task: dict):
    """Обрабатывает одну задачу"""
    task_id = task['id']
    user_id = task['user_id']
    chat_id = task['chat_id']
    task_type = task['task_type']
    
    logger.info(f"[TaskProcessor] Processing task {task_id}: {task_type} for user {user_id}")
    
    # Помечаем как выполняющуюся
    mark_task_processing(task_id)
    
    try:
        # Проверяем баланс
        cost = task['cost'] or 1
        balance = get_balance(user_id)
        
        if balance < cost:
            mark_task_failed(task_id, "Недостаточно генераций")
            bot.send_message(
                chat_id,
                f"❌ <b>Задача отменена</b>\n\n"
                f"Недостаточно генераций. Нужно: {cost}, у вас: {balance}",
                parse_mode='HTML'
            )
            return
        
        # Выполняем задачу в зависимости от типа
        if task_type == 'generate':
            result = await process_generate(bot, task)
        elif task_type == 'edit':
            result = await process_edit(bot, task)
        elif task_type == 'stylize':
            result = await process_stylize(bot, task)
        elif task_type == 'reference':
            result = await process_reference(bot, task)
        elif task_type == 'transform':
            result = await process_transform(bot, task)
        elif task_type == 'remove_bg':
            result = await process_remove_bg(bot, task)
        elif task_type == 'upscale':
            result = await process_upscale(bot, task)
        elif task_type == 'banner':
            result = await process_banner(bot, task)
        else:
            raise Exception(f"Unknown task type: {task_type}")
        
        # Списываем баланс
        decrease_balance(user_id, cost)
        new_balance = balance - cost
        
        # Отправляем результат
        from utils.image_generation import get_model_display_name
        model_display = get_model_display_name(task['model']) if task['model'] else ""
        
        # Проверяем, вернулся ли кортеж (image, url) или просто image
        original_url = None
        if isinstance(result, tuple):
            result, original_url = result
        
        # Формируем caption
        caption_parts = ["✅ <b>Готово!</b>"]
        
        if task['prompt']:
            caption_parts.append(f"📝 {task['prompt'][:100]}")
        
        if original_url:
            caption_parts.append(f"\n🔗 <a href='{original_url}'>Скачать оригинал (30 мин)</a>")

        if model_display:
            caption_parts.append(f"\n🤖 {model_display}")
        
        caption_parts.append(f"\n{BOT_SIGNATURE}")
        caption = "\n".join(caption_parts)

        try:
            if result is not None:
                # Если превью (сжатое фото) есть, отправляем его
                sent_message = bot.send_photo(
                    chat_id,
                    result,
                    caption=caption,
                    parse_mode='HTML'
                )
                result_file_id = sent_message.photo[-1].file_id if sent_message.photo else None
            else:
                # Если result вернул None (например, только ссылка), отправляем текст
                text_msg = (
                    f"✅ <b>Готово!</b>\n\n"
                    f"Изображение доступно по ссылке:\n"
                    f"🔗 <a href='{original_url}'><b>Скачать результат</b></a>\n\n"
                    f"🤖 {model_display}\n"
                    f"{BOT_SIGNATURE}"
                )
                bot.send_message(chat_id, text_msg, parse_mode='HTML')
                result_file_id = None
            
            mark_task_completed(task_id, result_file_id)

        except Exception as send_error:
            # Если Telegram отклонил фото, отправляем ссылку
            logger.error(f"[TaskProcessor] Failed to send photo, sending link instead: {send_error}")
            text_err = (
                f"✅ <b>Готово!</b>\n\n"
                f"Не удалось отобразить превью, но файл доступен по ссылке:\n"
                f"🔗 <a href='{original_url}'>Скачать оригинал</a>\n\n"
                f"{BOT_SIGNATURE}"
            )
            bot.send_message(chat_id, text_err, parse_mode='HTML')
            mark_task_completed(task_id, None)
        
        # Отправляем информацию о балансе
        bot.send_message(
            chat_id,
            f"💎 Осталось генераций: {new_balance}",
            parse_mode='HTML'
        )
        
        logger.info(f"[TaskProcessor] Task {task_id} completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[TaskProcessor] Task {task_id} failed: {error_msg}")
        mark_task_failed(task_id, error_msg)
        
        try:
            bot.send_message(
                chat_id,
                f"❌ <b>Ошибка генерации</b>\n\n{error_msg[:200]}\n\n"
                f"Попробуйте ещё раз.",
                parse_mode='HTML'
            )
        except:
            pass


# === НИЖЕ ИСПРАВЛЕННЫЕ ФУНКЦИИ ===

async def process_generate(bot, task: dict):
    """Генерация изображения"""
    from utils.image_generation import generate_image
    
    image_buffer = generate_image(
        model=task['model'],
        prompt=task['prompt'],
        aspect_ratio=task['aspect_ratio'] or '1:1'
    )
    
    # Загружаем на хостинг
    image_buffer.seek(0)
    url = upload_image(image_buffer.read())
    image_buffer.seek(0)
    
    return image_buffer, url


async def process_edit(bot, task: dict):
    """Редактирование изображения"""
    from utils.image_generation import edit_image
    
    file_info = bot.get_file(task['image_file_id'])
    image_bytes = bot.download_file(file_info.file_path)
    
    result_buffer = edit_image(
        model=task['model'],
        prompt=task['prompt'],
        image_bytes=image_bytes
    )
    
    # Загружаем на хостинг
    result_buffer.seek(0)
    url = upload_image(result_buffer.read())
    result_buffer.seek(0)
    
    return result_buffer, url


async def process_stylize(bot, task: dict):
    """Стилизация изображения"""
    from utils.image_tools import stylize_image
    
    file_info = bot.get_file(task['image_file_id'])
    image_bytes = bot.download_file(file_info.file_path)
    
    result_buffer = stylize_image(
        image_bytes=image_bytes,
        style=task['style'],
        model=task['model']
    )
    
    # Загружаем на хостинг
    result_buffer.seek(0)
    url = upload_image(result_buffer.read())
    result_buffer.seek(0)
    
    return result_buffer, url


async def process_reference(bot, task: dict):
    """Генерация по референсу"""
    from utils.image_tools import generate_with_reference
    
    file_info = bot.get_file(task['image_file_id'])
    reference_bytes = bot.download_file(file_info.file_path)
    
    result_buffer = generate_with_reference(
        reference_bytes=reference_bytes,
        prompt=task['prompt'],
        model=task['model']
    )
    
    # Загружаем на хостинг
    result_buffer.seek(0)
    url = upload_image(result_buffer.read())
    result_buffer.seek(0)
    
    return result_buffer, url


async def process_transform(bot, task: dict):
    """Трансформация по референсу"""
    from utils.image_tools import transform_with_reference
    
    ref_file_info = bot.get_file(task['image_file_id'])
    reference_bytes = bot.download_file(ref_file_info.file_path)
    
    target_file_info = bot.get_file(task['image2_file_id'])
    target_bytes = bot.download_file(target_file_info.file_path)
    
    result_buffer = transform_with_reference(
        reference_bytes=reference_bytes,
        target_bytes=target_bytes,
        model=task['model']
    )
    
    # Загружаем на хостинг
    result_buffer.seek(0)
    url = upload_image(result_buffer.read())
    result_buffer.seek(0)
    
    return result_buffer, url


async def process_remove_bg(bot, task: dict):
    """Удаление фона"""
    from utils.image_tools import remove_background
    
    file_info = bot.get_file(task['image_file_id'])
    image_bytes = bot.download_file(file_info.file_path)
    
    result_buffer = remove_background(image_bytes)
    
    # Загружаем на хостинг
    result_buffer.seek(0)
    url = upload_image(result_buffer.read())
    result_buffer.seek(0)
    
    return result_buffer, url


async def process_upscale(bot, task: dict):
    """Апскейл изображения"""
    from utils.image_tools import upscale_image
    
    file_info = bot.get_file(task['image_file_id'])
    image_bytes = bot.download_file(file_info.file_path)
    
    # upscale_image уже возвращает (compressed, original_url)
    return upscale_image(image_bytes)


async def process_banner(bot, task: dict):
    """Генерация баннера"""
    from utils.image_tools import generate_banner
    import json
    
    extra = json.loads(task['extra_data']) if task['extra_data'] else {}
    
    result_buffer = generate_banner(
        user_prompt=task['prompt'],
        style_prompt=extra.get('style_prompt', ''),
        aspect_ratio=task['aspect_ratio'] or '1:1'
    )
    
    # Загружаем на хостинг
    result_buffer.seek(0)
    url = upload_image(result_buffer.read())
    result_buffer.seek(0)
    
    return result_buffer, url


async def task_processor_loop(bot):
    """Основной цикл обработки задач"""
    logger.info("[TaskProcessor] Starting task processor...")
    reset_processing_to_pending()
    
    while True:
        try:
            tasks = get_pending_tasks(limit=5)
            for task in tasks:
                await process_task(bot, task)
                await asyncio.sleep(1)
            
            if not tasks:
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"[TaskProcessor] Loop error: {e}")
            await asyncio.sleep(5)
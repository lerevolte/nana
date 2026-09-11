"""
Обработчик задач генерации.
Выполняет задачи из очереди и отправляет результаты пользователям.
"""

import asyncio
import logging
from io import BytesIO

from utils.task_queue import (
    get_pending_tasks, mark_task_processing, mark_task_completed,
    mark_task_failed
)
from utils.db_utils import get_balance, decrease_balance, increase_balance
from utils.constants import BOT_SIGNATURE
from utils.closing import send_closing_notice
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

    cost = task['cost'] or 1
    charged = False  # Списали ли баланс — нужно для гарантированного возврата при ошибке

    try:
        # Проверяем баланс
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

        # Тяжёлая блокирующая генерация (requests к Segmind) выполняется в отдельном
        # потоке, чтобы НЕ замораживать event loop бота на время запроса/таймаута.
        result = await asyncio.to_thread(_execute_task, bot, task)

        # Списываем баланс ТОЛЬКО после успешной генерации
        decrease_balance(user_id, cost)
        charged = True
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
        send_closing_notice(bot, chat_id, task['user_id'])

        logger.info(f"[TaskProcessor] Task {task_id} completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[TaskProcessor] Task {task_id} failed: {error_msg}")

        # Если баланс успели списать — гарантированно возвращаем генерации
        refunded = False
        if charged:
            try:
                increase_balance(user_id, cost)
                refunded = True
                logger.info(f"[TaskProcessor] Refunded {cost} generations to user {user_id} (task {task_id})")
            except Exception as refund_err:
                logger.error(f"[TaskProcessor] REFUND FAILED for user {user_id} (task {task_id}): {refund_err}")

        mark_task_failed(task_id, error_msg)

        # Понятный пользователю текст ошибки + явное указание про генерации
        user_error = getattr(e, 'user_message', None) or "😔 Сервис временно перегружен."
        if refunded:
            balance_note = "💎 Генерации возвращены на баланс."
        elif not charged:
            balance_note = "💎 Генерации за эту попытку не списаны."
        else:
            balance_note = "💎 Если генерации списались — напишите в поддержку, вернём."

        try:
            bot.send_message(
                chat_id,
                f"❌ <b>Не удалось сгенерировать изображение</b>\n\n"
                f"{user_error}\n\n"
                f"{balance_note}\n"
                f"Попробуйте ещё раз через минуту.",
                parse_mode='HTML'
            )
        except:
            pass


# === НИЖЕ ИСПРАВЛЕННЫЕ ФУНКЦИИ ===

def _execute_task(bot, task: dict):
    """
    Синхронный диспетчер генерации. Выполняется в отдельном потоке
    (asyncio.to_thread), поэтому блокирующие requests к Segmind не морозят бота.
    """
    task_type = task['task_type']

    if task_type == 'generate':
        return process_generate(bot, task)
    elif task_type == 'edit':
        return process_edit(bot, task)
    elif task_type == 'stylize':
        return process_stylize(bot, task)
    elif task_type == 'reference':
        return process_reference(bot, task)
    elif task_type == 'transform':
        return process_transform(bot, task)
    elif task_type == 'remove_bg':
        return process_remove_bg(bot, task)
    elif task_type == 'upscale':
        return process_upscale(bot, task)
    elif task_type == 'banner':
        return process_banner(bot, task)
    else:
        raise Exception(f"Unknown task type: {task_type}")


def process_generate(bot, task: dict):
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


def process_edit(bot, task: dict):
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


def process_stylize(bot, task: dict):
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


def process_reference(bot, task: dict):
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


def process_transform(bot, task: dict):
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


def process_remove_bg(bot, task: dict):
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


def process_upscale(bot, task: dict):
    """Апскейл изображения"""
    from utils.image_tools import upscale_image
    
    file_info = bot.get_file(task['image_file_id'])
    image_bytes = bot.download_file(file_info.file_path)
    
    # upscale_image уже возвращает (compressed, original_url)
    return upscale_image(image_bytes)


def process_banner(bot, task: dict):
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


def _handle_interrupted_tasks(bot):
    """
    Обрабатывает задачи, прерванные перезапуском бота (статус 'processing').

    Раньше они сбрасывались в 'pending' и генерировались ЗАНОВО — а значит
    повторно тратили кредиты Segmind (картинка могла уже сгенерироваться до краша).
    Теперь помечаем их как failed и просим пользователя повторить вручную.
    Списания баланса в этот момент ещё не было (баланс списывается только
    после успешной генерации), поэтому возврат не требуется.
    """
    from utils.task_queue import get_processing_tasks

    interrupted = get_processing_tasks()
    for task in interrupted:
        try:
            mark_task_failed(task['id'], "Прервано перезапуском сервиса")
            bot.send_message(
                task['chat_id'],
                "⚠️ <b>Генерация прервана перезапуском сервиса</b>\n\n"
                "💎 Генерации за неё не списаны.\n"
                "Пожалуйста, отправьте запрос ещё раз.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"[TaskProcessor] Failed to handle interrupted task {task.get('id')}: {e}")

    if interrupted:
        logger.info(f"[TaskProcessor] Marked {len(interrupted)} interrupted task(s) as failed")


async def task_processor_loop(bot):
    """Основной цикл обработки задач"""
    logger.info("[TaskProcessor] Starting task processor...")
    _handle_interrupted_tasks(bot)

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
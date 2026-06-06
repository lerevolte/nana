import os
import uuid
import threading
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Настройки
IMAGE_HOST = os.getenv('IMAGE_HOST', 'localhost')  # Ваш публичный IP или домен
IMAGE_PORT = int(os.getenv('IMAGE_PORT', '8000'))
IMAGE_DIR = Path('temp_images')

# Создаём папку для изображений
IMAGE_DIR.mkdir(exist_ok=True)

# Флаг запущенного сервера
_server_started = False
_server_lock = threading.Lock()


class ImageHandler(SimpleHTTPRequestHandler):
    """Обработчик для раздачи изображений"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(IMAGE_DIR), **kwargs)
    
    def log_message(self, format, *args):
        # Логируем только ошибки
        if '404' in str(args) or '500' in str(args):
            logger.warning(f"[ImageServer] {args[0]}")
    
    def do_GET(self):
        # Добавляем CORS заголовки
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Отдаём файл
        super().do_GET()


def start_image_server():
    """Запускает HTTP сервер для раздачи изображений"""
    global _server_started
    
    with _server_lock:
        if _server_started:
            return
        
        def run_server():
            try:
                server = HTTPServer(('0.0.0.0', IMAGE_PORT), ImageHandler)
                logger.info(f"[ImageServer] Started on port {IMAGE_PORT}")
                server.serve_forever()
            except Exception as e:
                logger.error(f"[ImageServer] Failed to start: {e}")
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        _server_started = True


def upload_image(image_bytes: bytes, expiration: int = 600) -> str:
    """
    Сохраняет изображение и возвращает публичный URL.
    
    Args:
        image_bytes: Байты изображения
        expiration: Время жизни в секундах (для будущей очистки)
    
    Returns:
        Публичный URL изображения
    """
    # Запускаем сервер если ещё не запущен
    start_image_server()
    
    # Генерируем уникальное имя файла
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = IMAGE_DIR / filename
    
    # Сохраняем файл
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    
    # Формируем URL
    if IMAGE_HOST in ['localhost', '127.0.0.1'] or IMAGE_HOST[0].isdigit():
        url = f"http://{IMAGE_HOST}:{IMAGE_PORT}/{filename}"
    else:
        # Используем HTTPS и путь /images/, который мы настроили в Nginx
        url = f"https://{IMAGE_HOST}/images/{filename}"
    
    logger.info(f"[ImageHosting] Saved image: {filename}")
    
    # Запускаем отложенное удаление
    _schedule_deletion(filepath, expiration)
    
    return url


def upload_multiple_images(images_bytes: list, expiration: int = 600) -> list:
    """Загружает несколько изображений и возвращает список URL"""
    urls = []
    for img_bytes in images_bytes:
        url = upload_image(img_bytes, expiration)
        urls.append(url)
    return urls


def _schedule_deletion(filepath: Path, delay: int):
    """Планирует удаление файла через указанное время"""
    import time
    
    def delete_later():
        time.sleep(delay)
        try:
            if filepath.exists():
                filepath.unlink()
                logger.info(f"[ImageHosting] Deleted: {filepath.name}")
        except Exception as e:
            logger.warning(f"[ImageHosting] Failed to delete {filepath.name}: {e}")
    
    thread = threading.Thread(target=delete_later, daemon=True)
    thread.start()


def cleanup_old_images(max_age_seconds: int = 3600):
    """Удаляет старые изображения (можно вызывать периодически)"""
    import time
    
    now = time.time()
    count = 0
    
    for filepath in IMAGE_DIR.glob('*.jpg'):
        try:
            age = now - filepath.stat().st_mtime
            if age > max_age_seconds:
                filepath.unlink()
                count += 1
        except Exception as e:
            logger.warning(f"[ImageHosting] Cleanup error: {e}")
    
    if count > 0:
        logger.info(f"[ImageHosting] Cleaned up {count} old images")
#!/usr/bin/env python3
"""Простой HTTP сервер для раздачи изображений"""

import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

IMAGE_PORT = int(os.getenv('IMAGE_PORT', '8000'))
IMAGE_DIR = Path('temp_images')

# Создаём папку
IMAGE_DIR.mkdir(exist_ok=True)


class ImageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(IMAGE_DIR), **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', IMAGE_PORT), ImageHandler)
    server.timeout = 30
    print(f'Image server started on port {IMAGE_PORT}')
    server.serve_forever()
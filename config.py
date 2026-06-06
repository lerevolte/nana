import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN", "")

YANDEX_METRICA_ID = "106309492"

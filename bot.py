import telebot
from telebot import types
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

bot = telebot.TeleBot(TOKEN)

# Устанавливаем команды бота
def set_bot_commands():
    commands = [
        types.BotCommand('start', '🚀 Запустить бота'),
        types.BotCommand('menu', '📋 Главное меню'),
        types.BotCommand('create', '🎨 Создать изображение'),
        types.BotCommand('edit', '✏️ Редактировать изображение'),
        types.BotCommand('tools', '🛠 Инструменты'),
        types.BotCommand('model', '🤖 Выбрать модель'),
        types.BotCommand('balance', '💎 Мой баланс'),
        types.BotCommand('buy', '💰 Купить генерации'),
        types.BotCommand('invite', '👥 Пригласить друга'),
        types.BotCommand('promo', '🎁 Ввести промокод'),
        types.BotCommand('help', '❓ Помощь'),
    ]
    bot.set_my_commands(commands)

set_bot_commands()

# Регистрируем обработчики
from handlers import (
    start, create_image, callbacks, menu, model_selection, 
    payment, info, common, main_menu, edit_image, admin, tools, promo, closing_admin
)

common.register_handlers(bot)
admin.register_handlers(bot)
closing_admin.register_handlers(bot)
start.register_handlers(bot)
promo.register_handlers(bot)
tools.register_handlers(bot)  # Инструменты перед edit_image
edit_image.register_handlers(bot)
main_menu.register_handlers(bot)
create_image.register_handlers(bot)
callbacks.register_handlers(bot)
menu.register_handlers(bot)
model_selection.register_handlers(bot)
payment.register_handlers(bot)
info.register_handlers(bot)

# Запускаем фоновые задачи
from utils.background_tasks import start_background_tasks
start_background_tasks(bot)

if __name__ == '__main__':
    print('Бот запущен...')
    bot.infinity_polling()
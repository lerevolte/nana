import time
from handlers.admin import is_admin
from utils.closing import (
    load_recipients, RECIPIENTS_FILE, PAYMENTS_DISABLED,
    BROADCAST_TEXT, get_closing_keyboard
)

closing_state = {}


def register_handlers(bot):

    @bot.message_handler(commands=['closing_list'])
    def cmd_closing_list(message):
        if not is_admin(message.from_user.id):
            return
        ids = load_recipients()
        bot.send_message(
            message.chat.id,
            f"📋 <b>Список для уведомления о закрытии</b>\n\n"
            f"Файл: <code>{RECIPIENTS_FILE}</code>\n"
            f"Получателей: <b>{len(ids)}</b>\n"
            f"Оплата отключена: <b>{'да' if PAYMENTS_DISABLED else 'нет'}</b>\n\n"
            f"Рассылка по списку: /broadcast_closing",
            parse_mode="HTML"
        )

    @bot.message_handler(commands=['broadcast_closing'])
    def cmd_broadcast_closing(message):
        if not is_admin(message.from_user.id):
            return
        ids = sorted(load_recipients())
        if not ids:
            bot.send_message(message.chat.id, "❌ Список получателей пуст (closing_recipients.txt)")
            return
        closing_state[message.from_user.id] = ids
        bot.send_message(message.chat.id, BROADCAST_TEXT, reply_markup=get_closing_keyboard(), parse_mode="HTML")
        bot.send_message(
            message.chat.id,
            f"📢 <b>Рассылка о закрытии</b>\n\n"
            f"👥 Получателей: {len(ids)}\n"
            f"Выше — сообщение, которое они получат.\n\n"
            f"Отправьте <code>ДА</code> для подтверждения или /cancel",
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: m.from_user.id in closing_state)
    def confirm_broadcast_closing(message):
        if message.text == '/cancel':
            del closing_state[message.from_user.id]
            bot.send_message(message.chat.id, "❌ Рассылка отменена")
            return
        if message.text.upper() != 'ДА':
            bot.send_message(message.chat.id, "Отправьте <code>ДА</code> для подтверждения или /cancel", parse_mode="HTML")
            return
        ids = closing_state.pop(message.from_user.id)
        progress_msg = bot.send_message(message.chat.id, f"📤 Рассылка о закрытии... 0/{len(ids)}")
        success = 0
        failed = 0
        for i, user_id in enumerate(ids):
            try:
                bot.send_message(user_id, BROADCAST_TEXT, reply_markup=get_closing_keyboard(), parse_mode="HTML")
                success += 1
            except Exception:
                failed += 1
            if (i + 1) % 25 == 0:
                try:
                    bot.edit_message_text(
                        f"📤 Рассылка о закрытии... {i + 1}/{len(ids)}\n✅ Успешно: {success}\n❌ Ошибок: {failed}",
                        message.chat.id, progress_msg.message_id
                    )
                except Exception:
                    pass
            time.sleep(0.05)
        bot.edit_message_text(
            f"✅ <b>Рассылка о закрытии завершена</b>\n\n📬 Отправлено: {success}\n❌ Не доставлено: {failed}\n📊 Всего: {len(ids)}",
            message.chat.id, progress_msg.message_id, parse_mode="HTML"
        )

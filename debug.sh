#!/bin/bash

echo "=== ПОИСК ПРИЧИНЫ ОШИБКИ 500 ==="

# 1. Сначала перезапустим сервис, чтобы получить свежий лог старта
echo "Перезапуск сервиса..."
sudo systemctl restart bot_analytics
sleep 2

# 2. Делаем тестовый запрос локально (чтобы вызвать ошибку)
echo "Делаем запрос к API..."
curl -s -o /dev/null http://127.0.0.1:8001/analytics/kpi_filtered

# 3. Читаем журнал ошибок Python
echo -e "\n=== ЖУРНАЛ ОШИБОК (PYTHON TRACEBACK) ==="
# Ищем слова "Error", "Exception" или "Traceback" и показываем контекст
sudo journalctl -u bot_analytics --since "1 minute ago" --no-pager

echo -e "\n=== ЧТО ДЕЛАТЬ ДАЛЬШЕ ==="
echo "Если видите 'Access denied' -> Неверный логин/пароль в .env или коде."
echo "Если видите 'Unknown database' -> Неверное имя базы данных."
echo "Если видите 'Table doesn't exist' -> В коде указана таблица, которой нет в MySQL."
echo "Если видите 'ModuleNotFoundError' -> Какой-то библиотеки всё еще не хватает."
#!/bin/bash
# Скрипт для запуска бота в продакшен-режиме

echo "Запуск бота в продакшен-режиме..."

# Обновляем настройки webhook
echo "Обновление настроек webhook..."
./refresh_webhook.sh

# Запускаем keepalive
echo "Запуск keepalive..."
./start_keepalive.sh

# Запускаем мониторинг бота
echo "Запуск мониторинга бота..."
python bot_monitor.py &

# Запускаем бота в режиме webhook
echo "Запуск бота в режиме webhook..."
python run_bot_safe.py &

echo "Бот успешно запущен!"
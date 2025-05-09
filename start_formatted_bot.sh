#!/bin/bash

# Скрипт для запуска бота с новым форматированием тренировок
# Останавливает все существующие процессы бота и запускает новый экземпляр

# Останавливаем все существующие процессы Python, связанные с ботом
echo "Останавливаем существующие процессы бота..."
pkill -f "python.*bot"
sleep 2

# Очищаем сеанс Telegram API
echo "Очищаем сеанс Telegram API..."
curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/deleteWebhook" > /dev/null
curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getUpdates?offset=-1" > /dev/null

# Запускаем бота
echo "Запускаем бота..."
python start_formatted_bot.py
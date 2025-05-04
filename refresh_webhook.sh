#!/bin/bash
# Скрипт для обновления настройки webhook при перезапуске проекта

# Логирование
LOG_FILE="logs/webhook_refresh.log"
mkdir -p logs

echo "$(date) - Обновление webhook..." >> "$LOG_FILE"

# Обновляем webhook
python check_webhook.py delete >> "$LOG_FILE" 2>&1
sleep 2
python check_webhook.py set >> "$LOG_FILE" 2>&1

# Проверяем, что установка прошла успешно
python check_webhook.py check >> "$LOG_FILE" 2>&1

echo "$(date) - Обновление webhook завершено" >> "$LOG_FILE"

# Выводим URL для проверки
DOMAIN=$(grep REPLIT_DEV_DOMAIN .env | cut -d '=' -f 2)
if [ -z "$DOMAIN" ]; then
    DOMAIN="$REPLIT_DEV_DOMAIN"
fi

if [ -n "$DOMAIN" ]; then
    echo "Webhook URL: https://$DOMAIN/webhook/health"
fi

echo "Обновление webhook завершено. Подробности в логе: $LOG_FILE"
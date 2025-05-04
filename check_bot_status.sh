#!/bin/bash
# Скрипт для проверки статуса бота и webhook

echo "Проверка статуса Telegram бота..."

# Получаем домен Replit
DOMAIN=$(echo $REPLIT_DEV_DOMAIN)

if [ -z "$DOMAIN" ]; then
    echo "Ошибка: Не удалось получить домен Replit."
    exit 1
fi

# Получаем токен бота из переменной окружения или .env файла
TOKEN=$(grep TELEGRAM_TOKEN .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$TOKEN" ]; then
    # Пробуем получить из переменной окружения
    TOKEN=$TELEGRAM_TOKEN
fi

if [ -z "$TOKEN" ]; then
    echo "Ошибка: Не удалось получить токен Telegram бота."
    exit 1
fi

# Проверяем статус webhook через Telegram API
echo "Проверка настроек webhook через Telegram API..."
WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo")
echo $WEBHOOK_INFO | jq .

# Проверяем доступность health endpoint
echo -e "\nПроверка доступности health-endpoint..."
HEALTH_URL="https://$DOMAIN/webhook/health"
HEALTH_RESPONSE=$(curl -s "$HEALTH_URL")
echo $HEALTH_RESPONSE | jq .

# Проверяем запущенные процессы
echo -e "\nЗапущенные процессы бота:"
ps aux | grep -E 'main.py|gunicorn|keepalive' | grep -v grep

# Проверяем логи
echo -e "\nПоследние 10 строк из лога keepalive:"
tail -n 10 logs/keepalive.log 2>/dev/null || echo "Лог keepalive.log не найден"

echo -e "\nБот статус проверен!"
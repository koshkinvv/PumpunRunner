#!/bin/bash
# Скрипт для проверки доступности webhook

# Получаем домен Replit из переменных окружения
DOMAIN=$(grep REPLIT_DEV_DOMAIN .env | cut -d '=' -f 2)

# Если домен не найден в .env, пытаемся получить его из переменных окружения напрямую
if [ -z "$DOMAIN" ]; then
    DOMAIN="$REPLIT_DEV_DOMAIN"
fi

# Если домен не найден, выводим ошибку и выходим
if [ -z "$DOMAIN" ]; then
    echo "Ошибка: Переменная REPLIT_DEV_DOMAIN не найдена"
    exit 1
fi

# Формируем URL для проверки
URL="https://$DOMAIN/webhook/health"
echo "Проверяем доступность webhook по URL: $URL"

# Выполняем запрос
curl -s "$URL"

echo ""
echo "Проверка завершена."
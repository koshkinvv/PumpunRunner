#!/bin/bash
# Скрипт для предотвращения "засыпания" Replit путем регулярных запросов к webhook

# Настройки
WEBHOOK_HEALTH_URL=""
CHECK_INTERVAL=300  # 5 минут в секундах
LOG_FILE="logs/keepalive.log"

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Функция для логирования
log() {
    echo "$(date): $1" >> "$LOG_FILE"
}

# Получаем домен Replit из переменных окружения
get_domain() {
    # Сначала пытаемся получить из файла .env
    local domain=$(grep REPLIT_DEV_DOMAIN .env | cut -d '=' -f 2)
    
    # Если не нашли в .env, пытаемся получить из окружения
    if [ -z "$domain" ]; then
        domain="$REPLIT_DEV_DOMAIN"
    fi
    
    echo "$domain"
}

# Основной цикл
main() {
    log "Запуск скрипта keepalive..."
    
    # Получаем домен
    local domain=$(get_domain)
    if [ -z "$domain" ]; then
        log "ОШИБКА: Не удалось получить домен Replit. Скрипт не может продолжить работу."
        exit 1
    fi
    
    log "Домен Replit: $domain"
    WEBHOOK_HEALTH_URL="https://$domain/webhook/health"
    log "URL для проверки: $WEBHOOK_HEALTH_URL"
    
    # Бесконечный цикл опроса
    while true; do
        # Выполняем запрос и сохраняем результат
        response=$(curl -s "$WEBHOOK_HEALTH_URL")
        status=$?
        
        # Проверяем успешность запроса
        if [ $status -eq 0 ]; then
            log "Успешный запрос к $WEBHOOK_HEALTH_URL"
        else
            log "ОШИБКА: Не удалось выполнить запрос к $WEBHOOK_HEALTH_URL. Код: $status"
        fi
        
        # Ждем перед следующей проверкой
        sleep $CHECK_INTERVAL
    done
}

# Запускаем основную функцию
main
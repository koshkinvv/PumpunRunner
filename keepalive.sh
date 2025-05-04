#!/bin/bash

# Скрипт для пингования health-эндпоинта, чтобы сервер оставался активным

# Настройка
LOGFILE="logs/keepalive.log"
WEBHOOK_HEALTH_URL="http://localhost:5000/webhook/health"  # Локальный эндпоинт
REPLIT_DOMAIN="${REPLIT_DEV_DOMAIN:-19158b70-0a3f-4963-8a92-2b91605d3479-00-1hxlsvnxqgndx.kirk.replit.dev}"
PUBLIC_URL="https://${REPLIT_DOMAIN}/webhook/health"  # Публичный URL

# Интервал между запросами (в секундах)
INTERVAL=300  # 5 минут
MAX_FAILURES=3  # Максимальное количество подряд идущих ошибок
failure_count=0

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Функция логирования
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message" | tee -a "$LOGFILE"
}

# Функция для пингования эндпоинта
ping_endpoint() {
    local url="$1"
    local description="$2"
    
    log "Пингуем $description ($url)..."
    response=$(curl -s -w "\n%{http_code}" "$url" 2>&1)
    status_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" = "200" ]; then
        log "✅ $description проверка успешна (200 OK)"
        echo "$response_body" | grep -o '"status":"[^"]*"' >> "$LOGFILE" || echo "Статус не найден" >> "$LOGFILE"
        return 0
    else
        log "❌ $description проверка не удалась. Код: $status_code"
        log "Ответ: $response_body"
        return 1
    fi
}

# Функция для проверки обоих эндпоинтов
check_health() {
    local successful=false
    
    # Проверяем локальный эндпоинт
    if ping_endpoint "$WEBHOOK_HEALTH_URL" "Локальный"; then
        successful=true
    fi
    
    # Проверяем публичный эндпоинт
    if ping_endpoint "$PUBLIC_URL" "Публичный"; then
        successful=true
    fi
    
    # Возвращаем результат проверки
    if [ "$successful" = true ]; then
        failure_count=0
        return 0
    else
        ((failure_count++))
        log "Количество последовательных ошибок: $failure_count/$MAX_FAILURES"
        return 1
    fi
}

# Функция для проверки доступности внешних сервисов
check_external_connectivity() {
    log "Проверка соединения с Telegram API..."
    if curl -s "https://api.telegram.org" > /dev/null; then
        log "✅ Соединение с Telegram API доступно"
    else
        log "❌ Соединение с Telegram API недоступно"
    fi
}

# Выводим информацию о запуске
log "========================================"
log "Скрипт keepalive запущен"
log "REPL_SLUG: ${REPL_SLUG:-не задан}"
log "Webhook health URL: $WEBHOOK_HEALTH_URL"
log "Публичный URL: $PUBLIC_URL"
log "Интервал проверки: $INTERVAL секунд"
log "========================================"

# Проверяем внешние сервисы при запуске
check_external_connectivity

# Основной цикл
while true; do
    log "---------------------------------------"
    check_health
    
    # Проверяем, не превышен ли лимит ошибок
    if [ $failure_count -ge $MAX_FAILURES ]; then
        log "⚠️ Превышен лимит последовательных ошибок!"
        log "Проверка внешней связи..."
        check_external_connectivity
        
        # Сбрасываем счетчик ошибок
        failure_count=0
        
        log "Ожидаем следующей проверки..."
    fi
    
    log "Ожидание $INTERVAL секунд до следующей проверки..."
    sleep $INTERVAL
done
#!/bin/bash
# Скрипт обслуживания и мониторинга бота в режиме 24/7

# Создаем директорию для логов, если она отсутствует
mkdir -p logs

# Файл лога обслуживания
MAINTENANCE_LOG="logs/maintenance.log"

# Функция для записи в лог
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $MAINTENANCE_LOG
}

# Запись о запуске
log "Запуск скрипта обслуживания"

# Функция для проверки доступного дискового пространства
check_disk_space() {
    log "Проверка дискового пространства"
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    log "Использование диска: $DISK_USAGE%"
    
    if [ "$DISK_USAGE" -gt 90 ]; then
        log "ВНИМАНИЕ: Мало свободного места на диске ($DISK_USAGE%)"
        # Очистка старых логов при необходимости
        find logs -name "*.log" -type f -mtime +7 -delete
        log "Удалены логи старше 7 дней"
    fi
}

# Функция для проверки использования памяти
check_memory_usage() {
    log "Проверка использования памяти"
    MEMORY_USAGE=$(free -m | awk 'NR==2 {print int($3*100/$2)}')
    log "Использование памяти: $MEMORY_USAGE%"
    
    if [ "$MEMORY_USAGE" -gt 90 ]; then
        log "ВНИМАНИЕ: Высокое использование памяти ($MEMORY_USAGE%)"
    fi
}

# Функция для проверки работоспособности процессов
check_processes() {
    log "Проверка процессов бота"
    
    # Проверяем, работает ли скрипт run_24_7.sh
    if ! pgrep -f "bash.*run_24_7.sh" > /dev/null; then
        log "КРИТИЧЕСКАЯ ОШИБКА: Скрипт run_24_7.sh не запущен! Перезапуск..."
        nohup ./start_24_7.sh > logs/start_24_7_auto.log 2>&1 &
        log "Запущен скрипт start_24_7.sh"
    else
        log "Скрипт run_24_7.sh работает"
    fi
    
    # Проверяем, работает ли бот
    if ! pgrep -f "python.*run_telegram_bot.py" > /dev/null; then
        log "ОШИБКА: Бот не запущен!"
    else
        log "Бот работает"
    fi
    
    # Проверяем, работает ли веб-приложение
    if ! pgrep -f "python.*app.py" > /dev/null; then
        log "ОШИБКА: Веб-приложение не запущено!"
    else
        log "Веб-приложение работает"
    fi
}

# Функция для проверки файла здоровья бота
check_health_file() {
    log "Проверка файла здоровья бота"
    
    if [ -f bot_health.txt ]; then
        HEALTH_TIME=$(cat bot_health.txt)
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - HEALTH_TIME))
        
        log "Последнее обновление файла здоровья: $TIME_DIFF секунд назад"
        
        if [ $TIME_DIFF -gt 300 ]; then
            log "ВНИМАНИЕ: Файл здоровья устарел ($TIME_DIFF секунд)"
        fi
    else
        log "ОШИБКА: Файл здоровья отсутствует"
    fi
}

# Функция для проверки логов на наличие ошибок
check_logs_for_errors() {
    log "Проверка логов на наличие ошибок"
    
    # Ищем критические ошибки в логах бота
    ERROR_COUNT=$(grep -c -i "error\|exception\|traceback" logs/bot_output.log 2>/dev/null || echo "0")
    log "Найдено $ERROR_COUNT ошибок в логах бота"
    
    if [ "$ERROR_COUNT" -gt 0 ]; then
        log "Последние ошибки из лога бота:"
        grep -i "error\|exception\|traceback" logs/bot_output.log | tail -5 >> $MAINTENANCE_LOG
    fi
}

# Функция для очистки устаревших логов
clean_old_logs() {
    log "Очистка устаревших логов"
    
    # Удаление логов старше 30 дней
    find logs -name "*.log" -type f -mtime +30 -delete
    log "Удалены логи старше 30 дней"
    
    # Сжатие логов старше 7 дней
    find logs -name "*.log" -type f -mtime +7 -not -name "*.gz" | while read logfile; do
        gzip -f "$logfile"
        log "Сжат файл: $logfile"
    done
}

# Функция для обновления статистики
update_stats() {
    log "Обновление статистики"
    
    # Сбор статистики по запущенным процессам
    PROCESS_COUNT=$(ps aux | grep -v grep | grep -c python)
    log "Запущено $PROCESS_COUNT процессов Python"
    
    # Сбор статистики по использованию CPU
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}')
    log "Использование CPU: $CPU_USAGE%"
}

# Выполняем все функции обслуживания
check_disk_space
check_memory_usage
check_processes
check_health_file
check_logs_for_errors
update_stats

# Запускаем очистку логов раз в неделю (по воскресеньям)
if [ "$(date +%u)" = "7" ]; then
    log "Сегодня воскресенье, выполняем очистку старых логов"
    clean_old_logs
fi

log "Завершение скрипта обслуживания"
echo "Обслуживание завершено. Подробности в логе: $MAINTENANCE_LOG"
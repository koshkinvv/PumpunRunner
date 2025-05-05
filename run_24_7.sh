#!/bin/bash
# Скрипт для обеспечения непрерывной работы бота 24/7 на Reserved VM
# Запускает все необходимые компоненты и настраивает их автоматический перезапуск

# Настройка цветного вывода для лучшей читаемости
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директория логов
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

# Функция для логирования с временной меткой
log() {
    local level="$1"
    local message="$2"
    local color="$NC"
    
    case "$level" in
        "INFO") color="$GREEN" ;;
        "WARNING") color="$YELLOW" ;;
        "ERROR") color="$RED" ;;
        "STEP") color="$BLUE" ;;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" >> "$LOG_DIR/run_24_7.log"
}

# Функция для проверки, запущен ли процесс
is_process_running() {
    local process_name="$1"
    if pgrep -f "$process_name" > /dev/null; then
        return 0 # Процесс запущен
    else
        return 1 # Процесс не запущен
    fi
}

# Функция для остановки процесса
stop_process() {
    local process_name="$1"
    log "INFO" "Остановка процесса: $process_name"
    pkill -f "$process_name" || true
    sleep 2
}

# Функция для запуска процесса с автоматическим перезапуском
run_with_restart() {
    local cmd="$1"
    local name="$2"
    local log_file="$LOG_DIR/${name// /_}_$(date '+%Y%m%d_%H%M%S').log"
    local err_file="$LOG_DIR/${name// /_}_error_$(date '+%Y%m%d_%H%M%S').log"
    
    log "STEP" "Запуск $name с автоматическим перезапуском"
    
    # Запускаем процесс в фоне с перенаправлением вывода в логи
    while true; do
        log "INFO" "Запуск $name..."
        $cmd > "$log_file" 2> "$err_file" &
        local pid=$!
        log "INFO" "$name запущен с PID $pid"
        
        # Ждем завершения процесса
        wait $pid
        local exit_code=$?
        
        # Анализируем причину завершения
        if [ $exit_code -eq 0 ]; then
            log "WARNING" "$name завершился нормально с кодом 0, перезапуск..."
        else
            log "ERROR" "$name завершился с ошибкой (код $exit_code), перезапуск..."
            # Записываем последние 10 строк ошибок в лог
            log "ERROR" "Последние ошибки:"
            tail -n 10 "$err_file" | while read line; do
                log "ERROR" "  $line"
            done
        fi
        
        # Добавляем случайную задержку перед перезапуском (1-5 секунд)
        local delay=$((1 + RANDOM % 5))
        log "INFO" "Перезапуск через $delay секунд..."
        sleep $delay
    done
}

# Функция для очистки и подготовки окружения
prepare_environment() {
    log "STEP" "Подготовка окружения"
    
    # Останавливаем все существующие процессы
    log "INFO" "Останавливаем существующие процессы..."
    stop_process "python.*main.py"
    stop_process "python.*bot_monitor.py"
    stop_process "gunicorn.*main:app"
    stop_process "keep_alive.py"
    stop_process "keepalive.sh"
    
    # Создаем файл здоровья
    log "INFO" "Создание файла здоровья..."
    echo "$(date '+%Y-%m-%d %H:%M:%S')" > "bot_health.txt"
    
    # Делаем скрипты исполняемыми
    log "INFO" "Настройка прав доступа для скриптов..."
    chmod +x *.sh *.py
}

# Настройка регулярных напоминаний
setup_reminders() {
    log "STEP" "Настройка регулярных напоминаний"
    
    # Запускаем скрипт настройки cron, если он существует
    if [ -f "setup_cron.sh" ]; then
        log "INFO" "Запуск setup_cron.sh..."
        bash setup_cron.sh
    else
        log "WARNING" "Скрипт setup_cron.sh не найден, напоминания не будут настроены"
    fi
}

# Функция для установки переменных окружения из .env
load_env_vars() {
    log "STEP" "Загрузка переменных окружения"
    
    if [ -f ".env" ]; then
        log "INFO" "Загрузка переменных из .env файла..."
        export $(grep -v '^#' .env | xargs)
    else
        log "WARNING" ".env файл не найден"
    fi
}

# Основная функция запуска
main() {
    log "STEP" "Запуск системы непрерывной работы бота 24/7"
    
    # Загрузка переменных окружения
    load_env_vars
    
    # Подготовка окружения
    prepare_environment
    
    # Настройка регулярных напоминаний
    setup_reminders
    
    # Режим работы (webhook или polling)
    export USE_WEBHOOK=false
    log "INFO" "Установлен режим работы: polling (USE_WEBHOOK=false)"
    
    # Запуск Flask-приложения для мониторинга
    log "STEP" "Запуск веб-приложения для мониторинга (gunicorn)"
    run_with_restart "gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app" "Flask App" &
    
    # Ждем запуска Flask-приложения
    log "INFO" "Ждем запуск Flask-приложения..."
    sleep 5
    
    # Запуск скрипта мониторинга бота
    log "STEP" "Запуск скрипта мониторинга бота"
    run_with_restart "python bot_monitor.py" "Bot Monitor" &
    
    # Запуск скрипта keepalive
    log "STEP" "Запуск скрипта keepalive"
    run_with_restart "python keep_alive.py" "Keep Alive" &
    
    # Запуск основного бота
    log "STEP" "Запуск основного Telegram бота"
    run_with_restart "python main.py" "Telegram Bot" &
    
    # Запуск дополнительного монитора здоровья
    log "STEP" "Запуск дополнительного монитора здоровья"
    (
        while true; do
            echo "$(date '+%Y-%m-%d %H:%M:%S')" > "bot_health.txt"
            sleep 60
        done
    ) &
    
    log "INFO" "Все компоненты запущены и работают в фоновом режиме"
    log "INFO" "Система настроена на непрерывную работу 24/7"
    log "INFO" "Логи сохраняются в директории: $LOG_DIR"
    
    # Ожидаем завершения всех запущенных фоновых процессов
    # (что не должно произойти, так как они настроены на бесконечный перезапуск)
    wait
}

# Вызов основной функции
main
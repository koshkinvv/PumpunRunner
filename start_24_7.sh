#!/bin/bash
# Скрипт запуска бота в режиме 24/7

# Проверяем наличие директории для логов
if [ ! -d "logs" ]; then
    mkdir -p logs
fi

# Функция для записи в лог
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> logs/start_24_7.log
}

# Начинаем логирование
log "Запуск скрипта 24/7 для телеграм-бота"

# Проверяем, не запущен ли уже скрипт run_24_7.sh
if pgrep -f "bash.*run_24_7.sh" > /dev/null; then
    log "Скрипт run_24_7.sh уже запущен. Завершаем старый экземпляр..."
    pkill -f "bash.*run_24_7.sh"
    sleep 2
fi

# Проверяем и останавливаем все процессы бота
log "Остановка всех существующих процессов бота..."
pkill -f "python.*bot_modified.py" || true
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "python.*main.py" || true
sleep 3

# Делаем скрипты исполняемыми
chmod +x run_24_7.sh
chmod +x run_telegram_bot.py

# Запускаем скрипт run_24_7.sh
log "Запуск скрипта run_24_7.sh для поддержки 24/7 работы..."
nohup ./run_24_7.sh > logs/run_24_7_output.log 2>&1 &
SCRIPT_PID=$!

# Проверяем, что скрипт запустился
if ps -p $SCRIPT_PID > /dev/null; then
    log "Скрипт run_24_7.sh успешно запущен с PID: $SCRIPT_PID"
    echo "Скрипт run_24_7.sh запущен с PID: $SCRIPT_PID"
    exit 0
else
    log "ОШИБКА: Не удалось запустить скрипт run_24_7.sh"
    echo "ОШИБКА: Не удалось запустить скрипт run_24_7.sh. Проверьте logs/start_24_7.log"
    exit 1
fi
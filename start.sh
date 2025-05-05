#!/bin/bash
# Оптимизированный скрипт запуска для развертывания на Replit

# Создаем директорию для логов
mkdir -p logs

# Функция для записи в лог
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a logs/start.log
}

log "Запуск приложения для Replit с оптимизацией памяти"

# Очистка старых логов
log "Очистка старых логов..."
find logs -name "*.log" -type f -mtime +7 -delete
log "Старые логи очищены"

# Останавливаем все существующие процессы бота
log "Остановка существующих процессов..."
pkill -f "python.*bot_modified.py" || true
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "python.*main.py" || true
pkill -f "python.*getUpdates" || true
sleep 3

# Запускаем Telegram-бота с оптимизированным управлением памятью
log "Запуск Telegram-бота с оптимизацией памяти..."
python run_telegram_bot.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
log "Telegram-бот запущен с PID: $BOT_PID"

# Проверяем, что бот запустился
sleep 5
if ! ps -p $BOT_PID > /dev/null; then
    log "ОШИБКА: Telegram-бот не запустился! Проверьте логи."
    exit 1
fi

# Создаем или обновляем файл здоровья
echo "$(date '+%Y-%m-%d %H:%M:%S')" > bot_health.txt
log "Файл здоровья создан/обновлен"

# Запускаем Flask-приложение
log "Запуск Flask-приложения на порту 5000..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level info app:app
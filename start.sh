#!/bin/bash
# Простой скрипт запуска для развертывания на Replit

# Создаем директорию для логов
mkdir -p logs

# Функция для записи в лог
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a logs/start.log
}

log "Запуск приложения для Replit"

# Останавливаем все существующие процессы бота
log "Остановка существующих процессов..."
pkill -f "python.*bot_modified.py" || true
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "python.*main.py" || true
sleep 2

# Запускаем Telegram-бота
log "Запуск Telegram-бота..."
python run_telegram_bot.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
log "Telegram-бот запущен с PID: $BOT_PID"

# Проверяем, что бот запустился
sleep 3
if ! ps -p $BOT_PID > /dev/null; then
    log "ОШИБКА: Telegram-бот не запустился! Проверьте логи."
    exit 1
fi

# Создаем или обновляем файл здоровья
echo "$(date '+%Y-%m-%d %H:%M:%S')" > bot_health.txt
log "Файл здоровья создан/обновлен"

# Запускаем Flask-приложение
log "Запуск Flask-приложения на порту 5000..."
exec gunicorn --bind 0.0.0.0:5000 --access-logfile - --error-logfile - --log-level info app:app
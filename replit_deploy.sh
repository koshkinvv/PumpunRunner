#!/bin/bash
# Скрипт для запуска приложения в среде Replit Deployment

# Создаем директорию для логов
mkdir -p logs

# Функция для логирования
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a logs/deploy.log
}

log "Запуск скрипта развертывания"

# Проверяем доступность необходимых команд
if ! command -v gunicorn &> /dev/null; then
    log "ОШИБКА: gunicorn не найден. Завершение."
    exit 1
fi

# Проверяем наличие необходимых файлов
if [ ! -f "app.py" ]; then
    log "ОШИБКА: app.py не найден. Завершение."
    exit 1
fi

# Остановить существующие процессы бота и веб-приложения
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "gunicorn" || true
sleep 2

# Запускаем Telegram-бота
log "Запуск Telegram-бота"
python run_telegram_bot.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
log "Бот запущен с PID: $BOT_PID"

# Даем боту время на инициализацию
sleep 5

# Проверяем, что бот запустился
if ps -p $BOT_PID > /dev/null; then
    log "Telegram-бот успешно запущен"
else
    log "ПРЕДУПРЕЖДЕНИЕ: Telegram-бот не запустился!"
    # Пробуем запустить еще раз
    python run_telegram_bot.py > logs/bot_output_retry.log 2>&1 &
    BOT_PID=$!
    log "Повторный запуск бота с PID: $BOT_PID"
    sleep 5
fi

# Создаем или обновляем файл здоровья
echo "$(date '+%Y-%m-%d %H:%M:%S')" > bot_health.txt
log "Файл здоровья создан/обновлен"

# Запускаем веб-приложение через gunicorn
log "Запуск веб-приложения на порту 5000"
exec gunicorn --bind 0.0.0.0:5000 --timeout 120 app:app
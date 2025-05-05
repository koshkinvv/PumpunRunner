#!/bin/bash
# Скрипт для работы бота в режиме 24/7 на Reserved VM Replit

# Функция для создания файла здоровья
update_health_file() {
    echo "$(date +%s)" > bot_health.txt
}

# Создаем директории для логов
mkdir -p logs

# Логирование запуска
echo "$(date) - Запуск скрипта поддержки работы бота 24/7" >> logs/run_24_7.log

# Обновляем файл здоровья
update_health_file

# Остановка всех существующих процессов бота
echo "Остановка всех существующих процессов бота..."
pkill -f "python.*bot_modified.py" || true
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "python.*main.py" || true
sleep 3  # Даем время процессам завершиться

# Запуск обоих компонентов системы

# 1. Запуск бота в режиме polling
echo "Запуск Telegram бота..."
python run_telegram_bot.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
echo "Бот запущен с PID: $BOT_PID"

# 2. Запуск web-приложения для мониторинга
echo "Запуск веб-приложения для мониторинга..."
python app.py > logs/webapp_output.log 2>&1 &
WEBAPP_PID=$!
echo "Веб-приложение запущено с PID: $WEBAPP_PID"

# Запуск скрипта keep_alive для поддержания активности
echo "Запуск скрипта поддержания активности..."
python keep_alive.py > logs/keepalive_output.log 2>&1 &
KEEPALIVE_PID=$!

# Функция для проверки, работает ли процесс
check_process() {
    if ps -p $1 > /dev/null; then
        return 0  # Процесс работает
    else
        return 1  # Процесс не работает
    fi
}

# Функция для перезапуска бота
restart_bot() {
    echo "$(date) - Перезапуск бота..." >> logs/run_24_7.log
    pkill -f "python.*run_telegram_bot.py" || true
    sleep 3
    python run_telegram_bot.py > logs/bot_output.log 2>&1 &
    BOT_PID=$!
    echo "$(date) - Бот перезапущен с PID: $BOT_PID" >> logs/run_24_7.log
}

# Функция для перезапуска веб-приложения
restart_webapp() {
    echo "$(date) - Перезапуск веб-приложения..." >> logs/run_24_7.log
    pkill -f "python.*app.py" || true
    sleep 3
    python app.py > logs/webapp_output.log 2>&1 &
    WEBAPP_PID=$!
    echo "$(date) - Веб-приложение перезапущено с PID: $WEBAPP_PID" >> logs/run_24_7.log
}

# Функция для проверки файла здоровья
check_health_file() {
    if [ -f bot_health.txt ]; then
        HEALTH_TIME=$(cat bot_health.txt)
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - HEALTH_TIME))
        if [ $TIME_DIFF -gt 300 ]; then  # 5 минут
            echo "$(date) - Файл здоровья устарел, перезапуск бота..." >> logs/run_24_7.log
            return 1
        else
            return 0
        fi
    else
        echo "$(date) - Файл здоровья не найден, создание нового..." >> logs/run_24_7.log
        update_health_file
        return 0
    fi
}

# Основной цикл мониторинга и поддержания работы
echo "Запуск цикла мониторинга..."
while true; do
    # Обновляем файл здоровья
    update_health_file
    
    # Проверяем работу бота
    if ! check_process $BOT_PID; then
        echo "$(date) - Бот не работает, перезапуск..." >> logs/run_24_7.log
        restart_bot
    fi
    
    # Проверяем работу веб-приложения
    if ! check_process $WEBAPP_PID; then
        echo "$(date) - Веб-приложение не работает, перезапуск..." >> logs/run_24_7.log
        restart_webapp
    fi
    
    # Проверяем файл здоровья
    if ! check_health_file; then
        restart_bot
    fi
    
    # Сбрасываем буфер на диск для логов
    sync
    
    # Пауза перед следующей проверкой
    sleep 60
done
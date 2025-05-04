#!/bin/bash
# Скрипт для автоматического запуска полного комплекса: бот + мониторинг + веб-приложение
# Для использования в качестве единой точки входа

# Создаем лог-файл с датой и временем
LOG_DIR="logs"
mkdir -p $LOG_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/autorun_$TIMESTAMP.log"

echo "=== Автозапуск системы $(date) ===" > $LOG_FILE

# Запускаем бота и монитор в фоновом режиме
echo "Запуск бота и системы мониторинга..." >> $LOG_FILE
python run.py >> $LOG_FILE 2>&1 &
BOT_PID=$!
echo "Бот запущен с PID: $BOT_PID" >> $LOG_FILE

# Ждем несколько секунд, чтобы бот успел инициализироваться
sleep 5

# Запускаем веб-приложение в фоновом режиме
echo "Запуск веб-приложения..." >> $LOG_FILE
python run_webapp.py >> $LOG_FILE 2>&1 &
WEBAPP_PID=$!
echo "Веб-приложение запущено с PID: $WEBAPP_PID" >> $LOG_FILE

# Показываем информацию об успешном запуске
echo "Система запущена успешно!" >> $LOG_FILE
echo "Лог-файл: $LOG_FILE" >> $LOG_FILE
echo "Бот PID: $BOT_PID, Веб-приложение PID: $WEBAPP_PID" >> $LOG_FILE

# Выводим информацию в консоль
echo "=== Система запущена успешно! ==="
echo "Лог-файл: $LOG_FILE"
echo "Бот PID: $BOT_PID, Веб-приложение PID: $WEBAPP_PID"

# Ждем, пока оба процесса активны, и перезапускаем при необходимости
while true; do
    # Проверяем, работает ли бот
    if ! ps -p $BOT_PID > /dev/null; then
        echo "$(date) - Бот остановлен, перезапуск..." >> $LOG_FILE
        python run.py >> $LOG_FILE 2>&1 &
        BOT_PID=$!
        echo "$(date) - Бот перезапущен с PID: $BOT_PID" >> $LOG_FILE
    fi
    
    # Проверяем, работает ли веб-приложение
    if ! ps -p $WEBAPP_PID > /dev/null; then
        echo "$(date) - Веб-приложение остановлено, перезапуск..." >> $LOG_FILE
        python run_webapp.py >> $LOG_FILE 2>&1 &
        WEBAPP_PID=$!
        echo "$(date) - Веб-приложение перезапущено с PID: $WEBAPP_PID" >> $LOG_FILE
    fi
    
    # Ждем 60 секунд перед следующей проверкой
    sleep 60
done

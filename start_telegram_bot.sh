#!/bin/bash
# Скрипт для прямого запуска Telegram бота

# Выводим сообщение о запуске
echo "Запуск Telegram бота..."

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Останавливаем все существующие процессы бота
echo "Остановка всех существующих процессов бота..."
pkill -f "python.*bot_modified.py" || true
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "python.*main.py" || true
sleep 3  # Даем время процессам завершиться

# Запускаем бот напрямую через Python
echo "Запуск бота..."
python run_telegram_bot.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
echo "Бот запущен с PID: $BOT_PID"
echo "Логи сохраняются в logs/bot_output.log"

# Проверяем, что бот успешно запустился
sleep 5
if ps -p $BOT_PID > /dev/null; then
    echo "Бот успешно запущен и работает!"
else
    echo "Ошибка: бот не запустился. Проверьте логи."
    exit 1
fi

echo "Для остановки бота используйте команду: kill $BOT_PID"
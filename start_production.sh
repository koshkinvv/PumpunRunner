#!/bin/bash
# Скрипт для запуска бота в production-режиме со всеми системами мониторинга и уведомлений

# Определяем директорию скрипта
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Создаем файл для логирования
LOG_FILE="logs/production_start_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Запуск бота в production-режиме ==="
echo "Время запуска: $(date)"
echo "Директория: $SCRIPT_DIR"
echo "Лог-файл: $LOG_FILE"
echo ""

# Проверяем наличие всех необходимых файлов
echo "Проверка наличия необходимых файлов..."
REQUIRED_FILES=("run.py" "run_webapp.py" "autorun.sh" "notify_status.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "ОШИБКА: Файл $file не найден!"
        exit 1
    fi
done
echo "Все необходимые файлы найдены."
echo ""

# Проверяем доступность Telegram API
echo "Проверка доступности Telegram API..."
if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "ПРЕДУПРЕЖДЕНИЕ: Переменная окружения TELEGRAM_TOKEN не установлена."
    echo "Уведомления не будут работать без токена."
else
    # Проверяем соединение с Telegram API
    if curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe" | grep -q "\"ok\":true"; then
        echo "Соединение с Telegram API успешно установлено."
    else
        echo "ПРЕДУПРЕЖДЕНИЕ: Не удалось установить соединение с Telegram API."
        echo "Проверьте токен и подключение к интернету."
    fi
fi
echo ""

# Проверяем доступность PostgreSQL
echo "Проверка доступности базы данных PostgreSQL..."
if [ -z "$DATABASE_URL" ]; then
    echo "ПРЕДУПРЕЖДЕНИЕ: Переменная окружения DATABASE_URL не установлена."
else
    # Пытаемся проверить соединение с базой данных
    if command -v psql &> /dev/null; then
        # Пытаемся получить версию PostgreSQL
        if psql "$DATABASE_URL" -c "SELECT version();" > /dev/null 2>&1; then
            echo "Соединение с PostgreSQL успешно установлено."
        else
            echo "ПРЕДУПРЕЖДЕНИЕ: Не удалось установить соединение с PostgreSQL."
            echo "Проверьте строку подключения и доступность сервера."
        fi
    else
        echo "ПРИМЕЧАНИЕ: Утилита psql не установлена, пропускаем детальную проверку PostgreSQL."
    fi
fi
echo ""

# Останавливаем все существующие процессы бота
echo "Останавливаем все существующие процессы бота..."
pkill -f "python run.py" || true
pkill -f "python run_webapp.py" || true
pkill -f "python main.py" || true
pkill -f "python bot_monitor.py" || true
echo "Ожидаем завершения процессов..."
sleep 5
echo "Все существующие процессы остановлены."
echo ""

# Настраиваем cron-задачи для мониторинга
echo "Настройка cron-задач для мониторинга..."
if command -v crontab &> /dev/null; then
    ./setup_cron.sh
    echo "Cron-задачи настроены успешно."
else
    echo "ПРИМЕЧАНИЕ: cron не установлен, пропускаем настройку автоматических задач."
fi
echo ""

# Запускаем бота и мониторинг
echo "Запуск бота и системы мониторинга..."
./autorun.sh &
echo "Бот запущен в фоновом режиме."
echo ""

# Отправляем уведомление о запуске бота
echo "Отправка уведомления о запуске бота..."
if [ ! -z "$TELEGRAM_TOKEN" ]; then
    python notify_status.py --type startup
    echo "Уведомление отправлено."
else
    echo "Уведомление не отправлено (токен не установлен)."
fi
echo ""

echo "=== Бот успешно запущен в production-режиме ==="
echo "Для просмотра статуса посетите: http://0.0.0.0:5000"
echo "Для просмотра логов используйте: tail -f logs/*.log"
echo "Для остановки всех процессов используйте: pkill -f 'python run'"
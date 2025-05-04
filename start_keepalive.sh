#!/bin/bash

# Скрипт для запуска keepalive в фоновом режиме

# Проверяем, что скрипт keepalive.sh существует
if [ ! -f "keepalive.sh" ]; then
    echo "❌ Ошибка: Файл keepalive.sh не найден"
    exit 1
fi

# Делаем скрипт исполняемым
chmod +x keepalive.sh

# Проверяем, запущен ли уже скрипт keepalive
if pgrep -f "bash.*keepalive.sh" > /dev/null; then
    echo "⚠️ Скрипт keepalive.sh уже запущен"
    echo "Процессы keepalive:"
    ps aux | grep "bash.*keepalive.sh" | grep -v grep
    echo ""
    echo "Если вы хотите перезапустить скрипт, сначала остановите его:"
    echo "pkill -f 'bash.*keepalive.sh'"
    exit 0
fi

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Запускаем скрипт в фоновом режиме с перенаправлением вывода в лог-файл
echo "🚀 Запускаем keepalive.sh в фоновом режиме..."
nohup ./keepalive.sh > logs/keepalive.log 2>&1 &

# Сохраняем PID процесса
KEEPALIVE_PID=$!
echo "✅ Скрипт запущен с PID: $KEEPALIVE_PID"
echo "Вы можете проверить его статус командой:"
echo "ps aux | grep keepalive"
echo ""
echo "Для просмотра логов используйте:"
echo "tail -f logs/keepalive.log"
echo ""
echo "Для остановки скрипта используйте:"
echo "pkill -f 'bash.*keepalive.sh'"
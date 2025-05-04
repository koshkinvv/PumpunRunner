#!/bin/bash
# Скрипт для запуска keepalive в фоновом режиме

# Проверяем, запущен ли уже keepalive
pid=$(pgrep -f "bash keepalive.sh")
if [ -n "$pid" ]; then
    echo "Keepalive уже запущен с PID: $pid"
    exit 0
fi

# Делаем скрипт исполняемым, если он еще не такой
chmod +x keepalive.sh

# Запускаем keepalive в фоновом режиме
nohup ./keepalive.sh > /dev/null 2>&1 &
new_pid=$!

echo "Keepalive запущен в фоновом режиме с PID: $new_pid"
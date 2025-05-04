#!/bin/bash
# Скрипт для обеспечения постоянной работы бота
# Автоматически перезапускает процессы при их падении

echo "Запуск устойчивой системы с автоматическим перезапуском..."

# Функция для запуска и перезапуска процесса
run_with_restart() {
    local cmd="$1"
    local name="$2"
    local max_restarts=100
    local restart_count=0
    
    while [ $restart_count -lt $max_restarts ]; do
        echo "[$(date)] Запуск $name (попытка $((restart_count+1))/$max_restarts)..."
        $cmd &
        local pid=$!
        echo "[$(date)] $name запущен с PID $pid"
        
        # Ждем завершения процесса
        wait $pid
        local exit_code=$?
        
        echo "[$(date)] $name остановлен с кодом $exit_code"
        
        # Увеличиваем счетчик перезапусков
        restart_count=$((restart_count+1))
        
        # Если процесс завершился с ошибкой, перезапускаем его
        if [ $exit_code -ne 0 ]; then
            echo "[$(date)] $name завершился с ошибкой, перезапуск через 5 секунд..."
            sleep 5
        else
            echo "[$(date)] $name завершился нормально, перезапуск через 5 секунд..."
            sleep 5
        fi
    done
    
    echo "[$(date)] Достигнуто максимальное количество перезапусков для $name"
}

# Установка переменных окружения
export USE_WEBHOOK=true

# Запуск Flask-приложения
run_with_restart "gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app" "Flask App" &

# Даем Flask-приложению время для запуска
sleep 5

# Запуск keepalive
run_with_restart "./keepalive.sh" "Keepalive" &

# Запуск бота в режиме webhook
run_with_restart "python main.py" "Telegram Bot" &

# Ждем завершения всех запущенных фоновых процессов
wait

echo "Все процессы завершены"
#!/bin/bash
# Главный скрипт для запуска бота в режиме непрерывной работы 24/7
# Запускает всю необходимую инфраструктуру мониторинга и автовосстановления

# Цветной вывод
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}Запуск Telegram бота в режиме 24/7 на Reserved VM${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Создаем директории для логов
mkdir -p logs

# Функция для проверки запущен ли процесс
is_running() {
    pgrep -f "$1" > /dev/null
}

# Останавливаем все существующие процессы
echo -e "${YELLOW}Остановка всех существующих процессов...${NC}"
pkill -f "main.py" || true
pkill -f "bot_monitor.py" || true
pkill -f "keep_alive.py" || true
pkill -f "auto_recovery.py" || true
pkill -f "run_24_7.sh" || true
pkill -f "gunicorn" || true

# Ждем завершения всех процессов
sleep 3

# Делаем скрипты исполняемыми
echo -e "${YELLOW}Установка прав на исполнение для скриптов...${NC}"
chmod +x *.sh *.py 2>/dev/null || true

# Запускаем основной скрипт работы 24/7
echo -e "${YELLOW}Запуск основного скрипта непрерывной работы...${NC}"
nohup bash run_24_7.sh > logs/run_24_7_output.log 2>&1 &
RUN_PID=$!
echo "run_24_7.sh запущен с PID: $RUN_PID"

# Ждем запуска основных компонентов
echo -e "${YELLOW}Ожидание запуска основных компонентов...${NC}"
sleep 15

# Запускаем скрипт автоматического восстановления
echo -e "${YELLOW}Запуск системы автоматического восстановления...${NC}"
nohup python auto_recovery.py > logs/auto_recovery_output.log 2>&1 &
RECOVERY_PID=$!
echo "auto_recovery.py запущен с PID: $RECOVERY_PID"

# Проверяем, что все компоненты запущены
echo -e "${YELLOW}Проверка запущенных компонентов...${NC}"
sleep 5

check_components() {
    local all_running=true
    
    # Проверяем основные компоненты
    if ! is_running "main.py"; then
        echo "❌ Telegram Bot (main.py) не запущен"
        all_running=false
    else
        echo "✅ Telegram Bot (main.py) запущен"
    fi
    
    if ! is_running "bot_monitor.py"; then
        echo "❌ Монитор бота (bot_monitor.py) не запущен"
        all_running=false
    else
        echo "✅ Монитор бота (bot_monitor.py) запущен"
    fi
    
    if ! is_running "keep_alive.py"; then
        echo "❌ Keep Alive (keep_alive.py) не запущен"
        all_running=false
    else
        echo "✅ Keep Alive (keep_alive.py) запущен"
    fi
    
    if ! is_running "gunicorn"; then
        echo "❌ Web-приложение (gunicorn) не запущен"
        all_running=false
    else
        echo "✅ Web-приложение (gunicorn) запущен"
    fi
    
    if ! is_running "auto_recovery.py"; then
        echo "❌ Система восстановления (auto_recovery.py) не запущена"
        all_running=false
    else
        echo "✅ Система восстановления (auto_recovery.py) запущена"
    fi
    
    local return_code=0
    if ! $all_running; then
        return_code=1
    fi
    echo $return_code
    return $return_code
}

# Проверяем компоненты
if check_components; then
    echo -e "${GREEN}Все компоненты успешно запущены!${NC}"
else
    echo -e "${YELLOW}Некоторые компоненты не запущены, ожидаем их автоматического запуска...${NC}"
    sleep 15
    
    if check_components; then
        echo -e "${GREEN}Все компоненты успешно запущены!${NC}"
    else
        echo -e "${YELLOW}Предупреждение: Некоторые компоненты не запустились автоматически.${NC}"
        echo -e "${YELLOW}Система автовосстановления попытается их запустить.${NC}"
    fi
fi

echo -e "${GREEN}=========================================================${NC}"
echo -e "${GREEN}Бот успешно запущен в режиме 24/7 на Reserved VM${NC}"
echo -e "${GREEN}Система будет автоматически восстанавливаться при сбоях${NC}"
echo -e "${GREEN}Логи сохраняются в директории: logs/${NC}"
echo -e "${GREEN}=========================================================${NC}"
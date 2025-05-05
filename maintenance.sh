#!/bin/bash
# Скрипт для обслуживания системы непрерывной работы бота
# Включает очистку логов, проверку состояния и возможность перезапуска

# Цветной вывод
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для отображения меню
show_menu() {
    clear
    echo -e "${BLUE}=====================================================${NC}"
    echo -e "${GREEN}Обслуживание системы непрерывной работы бота 24/7${NC}"
    echo -e "${BLUE}=====================================================${NC}"
    echo ""
    echo -e "${YELLOW}1.${NC} Проверить состояние бота"
    echo -e "${YELLOW}2.${NC} Перезапустить систему"
    echo -e "${YELLOW}3.${NC} Очистить старые логи"
    echo -e "${YELLOW}4.${NC} Архивировать логи"
    echo -e "${YELLOW}5.${NC} Показать последние ошибки"
    echo -e "${YELLOW}6.${NC} Показать использование ресурсов"
    echo -e "${YELLOW}0.${NC} Выйти"
    echo ""
    echo -n "Выберите действие (0-6): "
}

# Функция для проверки состояния бота
check_status() {
    echo -e "${BLUE}Проверка состояния бота...${NC}"
    echo ""
    
    # Проверка файла здоровья
    if [ -f "bot_health.txt" ]; then
        health_time=$(cat bot_health.txt)
        echo -e "Файл здоровья: ${GREEN}Существует${NC}"
        echo -e "Последнее обновление: ${GREEN}$health_time${NC}"
        
        # Проверка актуальности файла здоровья
        current_time=$(date +%s)
        health_time_sec=$(date -d "$health_time" +%s 2>/dev/null)
        if [ $? -eq 0 ]; then
            time_diff=$((current_time - health_time_sec))
            if [ $time_diff -gt 300 ]; then
                echo -e "Статус: ${RED}Устарел ($time_diff секунд назад)${NC}"
            else
                echo -e "Статус: ${GREEN}Актуален${NC}"
            fi
        else
            echo -e "Статус: ${YELLOW}Невозможно определить возраст${NC}"
        fi
    else
        echo -e "Файл здоровья: ${RED}Отсутствует${NC}"
    fi
    
    echo ""
    
    # Проверка запущенных процессов
    echo "Запущенные процессы:"
    echo "-----------------"
    
    if pgrep -f "python.*main.py" > /dev/null; then
        echo -e "Основной бот: ${GREEN}Запущен${NC}"
    else
        echo -e "Основной бот: ${RED}Не запущен${NC}"
    fi
    
    if pgrep -f "python.*bot_monitor.py" > /dev/null; then
        echo -e "Монитор бота: ${GREEN}Запущен${NC}"
    else
        echo -e "Монитор бота: ${RED}Не запущен${NC}"
    fi
    
    if pgrep -f "gunicorn.*main:app" > /dev/null; then
        echo -e "Веб-интерфейс: ${GREEN}Запущен${NC}"
    else
        echo -e "Веб-интерфейс: ${RED}Не запущен${NC}"
    fi
    
    if pgrep -f "python.*auto_recovery.py" > /dev/null; then
        echo -e "Система восстановления: ${GREEN}Запущена${NC}"
    else
        echo -e "Система восстановления: ${RED}Не запущена${NC}"
    fi
    
    if pgrep -f "python.*keep_alive.py" > /dev/null; then
        echo -e "Keep Alive: ${GREEN}Запущен${NC}"
    else
        echo -e "Keep Alive: ${RED}Не запущен${NC}"
    fi
    
    echo ""
    echo "Нажмите Enter для возврата в меню..."
    read
}

# Функция для перезапуска системы
restart_system() {
    echo -e "${BLUE}Перезапуск системы...${NC}"
    echo ""
    echo -e "${YELLOW}Останавливаем все процессы...${NC}"
    
    pkill -f "python.*main.py" || true
    pkill -f "python.*bot_monitor.py" || true
    pkill -f "python.*auto_recovery.py" || true
    pkill -f "python.*keep_alive.py" || true
    pkill -f "gunicorn.*main:app" || true
    pkill -f "bash.*run_24_7.sh" || true
    
    echo "Ждем завершения процессов..."
    sleep 5
    
    echo -e "${YELLOW}Запускаем систему...${NC}"
    bash start_24_7.sh
    
    echo ""
    echo "Система перезапущена. Нажмите Enter для возврата в меню..."
    read
}

# Функция для очистки старых логов
clean_logs() {
    echo -e "${BLUE}Очистка старых логов...${NC}"
    echo ""
    
    if [ ! -d "logs" ]; then
        echo "Директория logs не существует."
        echo ""
        echo "Нажмите Enter для возврата в меню..."
        read
        return
    fi
    
    # Подсчет количества и размера логов
    log_count=$(find logs -type f | wc -l)
    log_size=$(du -sh logs | cut -f1)
    
    echo -e "Текущее количество файлов логов: ${YELLOW}$log_count${NC}"
    echo -e "Общий размер логов: ${YELLOW}$log_size${NC}"
    echo ""
    
    echo -n "Очистить логи старше (дней, по умолчанию 7): "
    read days
    
    # Если пользователь не ввел значение, используем 7 дней
    if [ -z "$days" ]; then
        days=7
    fi
    
    # Проверяем, является ли введенное значение числом
    if ! [[ "$days" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Ошибка: '$days' не является числом.${NC}"
        echo ""
        echo "Нажмите Enter для возврата в меню..."
        read
        return
    fi
    
    echo -e "${YELLOW}Удаление логов старше $days дней...${NC}"
    
    # Поиск и удаление файлов старше указанного количества дней
    old_logs=$(find logs -type f -mtime +$days)
    old_count=$(echo "$old_logs" | grep -v '^$' | wc -l)
    
    if [ $old_count -eq 0 ]; then
        echo "Нет логов старше $days дней."
    else
        echo "Найдено $old_count логов старше $days дней:"
        echo "$old_logs" | while read log; do
            echo "  - $log"
            rm "$log"
        done
        echo -e "${GREEN}Старые логи удалены.${NC}"
    fi
    
    echo ""
    echo "Нажмите Enter для возврата в меню..."
    read
}

# Функция для архивирования логов
archive_logs() {
    echo -e "${BLUE}Архивирование логов...${NC}"
    echo ""
    
    if [ ! -d "logs" ]; then
        echo "Директория logs не существует."
        echo ""
        echo "Нажмите Enter для возврата в меню..."
        read
        return
    fi
    
    # Создаем директорию для архивов, если она не существует
    mkdir -p logs_archive
    
    # Запрашиваем опции архивирования
    echo -n "Архивировать логи старше (дней, по умолчанию все): "
    read days
    
    archive_name="logs_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    if [ -z "$days" ] || ! [[ "$days" =~ ^[0-9]+$ ]]; then
        # Архивируем все логи
        echo -e "${YELLOW}Архивирование всех логов...${NC}"
        tar -czf "logs_archive/$archive_name" logs
    else
        # Архивируем логи старше указанного количества дней
        echo -e "${YELLOW}Архивирование логов старше $days дней...${NC}"
        find logs -type f -mtime +$days -print0 | tar -czf "logs_archive/$archive_name" --null -T -
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Архив создан: logs_archive/$archive_name${NC}"
        
        # Спрашиваем, нужно ли удалить заархивированные логи
        echo -n "Удалить заархивированные логи? (y/n, по умолчанию n): "
        read delete
        
        if [ "$delete" = "y" ] || [ "$delete" = "Y" ]; then
            if [ -z "$days" ] || ! [[ "$days" =~ ^[0-9]+$ ]]; then
                # Удаляем все логи
                rm -f logs/*
                echo -e "${GREEN}Все логи удалены.${NC}"
            else
                # Удаляем логи старше указанного количества дней
                find logs -type f -mtime +$days -delete
                echo -e "${GREEN}Удалены логи старше $days дней.${NC}"
            fi
        fi
    else
        echo -e "${RED}Ошибка при создании архива.${NC}"
    fi
    
    echo ""
    echo "Нажмите Enter для возврата в меню..."
    read
}

# Функция для отображения последних ошибок
show_errors() {
    echo -e "${BLUE}Последние ошибки из логов...${NC}"
    echo ""
    
    if [ ! -d "logs" ]; then
        echo "Директория logs не существует."
        echo ""
        echo "Нажмите Enter для возврата в меню..."
        read
        return
    fi
    
    # Поиск ошибок в файлах логов
    echo -e "${YELLOW}Поиск ошибок в логах...${NC}"
    
    # Поиск по ключевым словам ошибок
    grep_result=$(grep -i -e "error" -e "exception" -e "traceback" -e "failed" -e "critical" logs/* 2>/dev/null | tail -n 50)
    
    if [ -z "$grep_result" ]; then
        echo "Ошибки не найдены."
    else
        echo "Последние 50 ошибок из всех логов:"
        echo "---------------------------------"
        echo "$grep_result"
    fi
    
    echo ""
    echo "Нажмите Enter для возврата в меню..."
    read
}

# Функция для отображения использования ресурсов
show_resources() {
    echo -e "${BLUE}Использование ресурсов...${NC}"
    echo ""
    
    echo -e "${YELLOW}Использование CPU:${NC}"
    ps -eo pid,ppid,cmd,%cpu,%mem --sort=-%cpu | head -n 11
    
    echo -e "\n${YELLOW}Использование памяти:${NC}"
    ps -eo pid,ppid,cmd,%cpu,%mem --sort=-%mem | head -n 11
    
    echo -e "\n${YELLOW}Общее использование системы:${NC}"
    free -h
    
    echo -e "\n${YELLOW}Использование диска:${NC}"
    df -h .
    
    echo ""
    echo "Нажмите Enter для возврата в меню..."
    read
}

# Основной цикл
while true; do
    show_menu
    read choice
    
    case $choice in
        1)
            check_status
            ;;
        2)
            restart_system
            ;;
        3)
            clean_logs
            ;;
        4)
            archive_logs
            ;;
        5)
            show_errors
            ;;
        6)
            show_resources
            ;;
        0)
            echo "Выход из программы..."
            exit 0
            ;;
        *)
            echo "Некорректный выбор. Пожалуйста, выберите опцию 0-6."
            echo "Нажмите Enter для продолжения..."
            read
            ;;
    esac
done
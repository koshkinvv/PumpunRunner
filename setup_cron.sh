#!/bin/bash
# Скрипт для настройки cron-задач для мониторинга бота

# Проверяем, установлен ли cron
if ! command -v crontab &> /dev/null; then
    echo "cron не установлен!"
    exit 1
fi

# Полный путь к текущей директории
CURRENT_DIR=$(pwd)

# Создаем временный файл для crontab
TEMP_CRONTAB=$(mktemp)

# Получаем текущий crontab
crontab -l > $TEMP_CRONTAB 2>/dev/null

# Добавляем задачи
echo "# Автоматический запуск бота при перезагрузке" >> $TEMP_CRONTAB
echo "@reboot cd $CURRENT_DIR && ./autorun.sh >> logs/cron_autorun.log 2>&1" >> $TEMP_CRONTAB
echo "" >> $TEMP_CRONTAB

echo "# Проверка состояния бота каждые 30 минут" >> $TEMP_CRONTAB
echo "*/30 * * * * cd $CURRENT_DIR && python notify_status.py --check >> logs/cron_check.log 2>&1" >> $TEMP_CRONTAB
echo "" >> $TEMP_CRONTAB

echo "# Отправка регулярных отчетов о состоянии бота (раз в 6 часов)" >> $TEMP_CRONTAB
echo "0 */6 * * * cd $CURRENT_DIR && python notify_status.py >> logs/cron_report.log 2>&1" >> $TEMP_CRONTAB
echo "" >> $TEMP_CRONTAB

# Устанавливаем новый crontab
crontab $TEMP_CRONTAB

# Удаляем временный файл
rm $TEMP_CRONTAB

echo "Cron-задачи настроены успешно!"
echo "Проверьте текущие задачи:"
crontab -l
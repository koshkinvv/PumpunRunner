#!/bin/bash

# Скрипт для настройки регулярного запуска напоминаний через cron
# После настройки, reminders будет запускаться каждые 15 минут
# Это позволит всем пользователям получать напоминания в 20:00 по их местному времени

# Определяем пути
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_PATH=$(which python3)
REMINDERS_SCRIPT="$SCRIPT_DIR/run_reminders.py"

# Проверяем наличие скрипта
if [ ! -f "$REMINDERS_SCRIPT" ]; then
  echo "Ошибка: Скрипт напоминаний не найден по пути $REMINDERS_SCRIPT"
  exit 1
fi

# Делаем скрипты исполняемыми
chmod +x "$REMINDERS_SCRIPT"

# Создаем временный файл для crontab
TEMP_CRONTAB=$(mktemp)

# Экспортируем текущий crontab
crontab -l > "$TEMP_CRONTAB" 2>/dev/null || echo "" > "$TEMP_CRONTAB"

# Проверяем, не добавлено ли уже наше задание
if ! grep -q "$REMINDERS_SCRIPT" "$TEMP_CRONTAB"; then
  # Добавляем задание для запуска каждые 15 минут
  echo "*/15 * * * * cd $SCRIPT_DIR && $PYTHON_PATH $REMINDERS_SCRIPT >> $SCRIPT_DIR/logs/reminders_cron.log 2>&1" >> "$TEMP_CRONTAB"
  
  # Устанавливаем новый crontab
  crontab "$TEMP_CRONTAB"
  
  echo "Задание cron успешно добавлено для запуска скрипта напоминаний каждые 15 минут"
else
  echo "Задание cron для скрипта напоминаний уже существует"
fi

# Удаляем временный файл
rm "$TEMP_CRONTAB"

echo "Настройка завершена!"
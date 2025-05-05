#!/bin/bash

# Запускаем бота в режиме webhook-монитора
# Этот скрипт должен использоваться в воркфлоу bot_runner

# Запускаем webhook_monitor.py для поддержки webhook
echo "Запуск webhook_monitor.py..."
exec python webhook_monitor.py
"""
Скрипт для настройки workflow запуска веб-приложения с улучшенной стабильностью.
Создает скрипты для запуска стабильного бота и веб-приложения с правильной обработкой конфликтов.
"""
import os
import subprocess
import sys

def main():
    """Основная функция для настройки workflow."""
    # Создаем скрипт запуска стабильного веб-приложения
    web_runner_script = """#!/bin/bash

# Скрипт для запуска стабильного веб-сервера с поддержкой бота
# Использует исправленную версию скрипта запуска для избежания конфликтов

echo "Запуск стабильного веб-сервера и бота..."
python run_updated_webapp_fixed.py
"""
    
    with open("fixed_web_runner.sh", "w") as f:
        f.write(web_runner_script)
    
    # Делаем скрипт исполняемым
    os.chmod("fixed_web_runner.sh", 0o755)
    
    # Создаем скрипт запуска только бота
    bot_runner_script = """#!/bin/bash

# Скрипт для запуска бота с улучшенной стабильностью
# Использует новый скрипт run_fixed_bot.py для запуска бота,
# который автоматически завершает конфликтующие экземпляры бота
# и сбрасывает сессию Telegram API перед запуском

echo "Запуск стабильного бота с исправленной функциональностью..."
python run_fixed_bot.py
"""
    
    with open("stable_bot_workflow.sh", "w") as f:
        f.write(bot_runner_script)
    
    # Делаем скрипт исполняемым
    os.chmod("stable_bot_workflow.sh", 0o755)
    
    print("Скрипты запуска созданы:")
    print("1. fixed_web_runner.sh - Запуск стабильного веб-сервера с ботом")
    print("2. stable_bot_workflow.sh - Запуск только бота в стабильном режиме")
    print("\nТеперь вы можете запустить один из этих скриптов:")
    print("./fixed_web_runner.sh - для веб-сервера")
    print("./stable_bot_workflow.sh - только для бота")

if __name__ == "__main__":
    main()
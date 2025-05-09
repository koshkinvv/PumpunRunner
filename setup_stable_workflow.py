#!/usr/bin/env python3
"""
Скрипт для настройки стабильного workflow в Replit.
Создает необходимые конфигурационные файлы и регистрирует workflow для запуска бота.
"""
import os
import json
import subprocess
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/setup_workflow.log')
    ]
)
logger = logging.getLogger(__name__)

def create_logs_directory():
    """Создает директорию для логов, если она не существует"""
    try:
        os.makedirs('logs', exist_ok=True)
        logger.info("Директория logs создана или уже существует")
    except Exception as e:
        logger.error(f"Ошибка при создании директории logs: {e}")
        raise

def restart_workflow(name="stable_bot"):
    """Перезапускает workflow или создает новый, если он не существует"""
    try:
        # Проверим существующие workflows
        result = subprocess.run(['replit', 'workflow', 'list'], capture_output=True, text=True)
        logger.info(f"Список существующих workflows: {result.stdout}")
        
        # Создаем или перезапускаем workflow
        if name in result.stdout:
            # Workflow существует, перезапускаем
            subprocess.run(['replit', 'workflow', 'restart', name], check=True)
            logger.info(f"Workflow {name} перезапущен")
        else:
            # Создаем новый workflow
            logger.info(f"Workflow {name} не найден, создаем новый")
            create_workflow(name)
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при работе с workflow: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")

def create_workflow(name="stable_bot"):
    """Создает новый workflow с запуском стабильного бота"""
    try:
        # Создаем конфигурацию workflow
        workflow_config = {
            "name": name,
            "tasks": [
                {
                    "name": "Run Stable Bot",
                    "command": "./stable_bot_workflow.sh"
                }
            ]
        }
        
        # Записываем конфигурацию во временный файл
        with open('temp_workflow.json', 'w') as f:
            json.dump(workflow_config, f)
        
        # Создаем workflow из файла
        subprocess.run(['replit', 'workflow', 'create', '--file', 'temp_workflow.json'], check=True)
        logger.info(f"Workflow {name} успешно создан")
        
        # Удаляем временный файл
        os.remove('temp_workflow.json')
    except Exception as e:
        logger.error(f"Ошибка при создании workflow: {e}")
        raise

def create_runner_scripts():
    """Создает скрипты запуска и делает их исполняемыми"""
    try:
        # Скрипт для запуска стабильного бота
        bot_script = """#!/bin/bash

# Скрипт для запуска бота с улучшенной стабильностью
# Использует новый скрипт run_fixed_bot.py для запуска бота,
# который автоматически завершает конфликтующие экземпляры бота
# и сбрасывает сессию Telegram API перед запуском

echo "Запуск стабильного бота с исправленной функциональностью..."
python run_fixed_bot.py
"""
        with open('stable_bot_workflow.sh', 'w') as f:
            f.write(bot_script)
        os.chmod('stable_bot_workflow.sh', 0o755)
        logger.info("Скрипт запуска стабильного бота создан: stable_bot_workflow.sh")
        
        # Скрипт для запуска стабильного веб-сервера
        web_script = """#!/bin/bash

# Скрипт для запуска стабильного веб-сервера с поддержкой бота
# Использует исправленную версию скрипта запуска для избежания конфликтов

echo "Запуск стабильного веб-сервера и бота..."
python run_updated_webapp_fixed.py
"""
        with open('fixed_web_runner.sh', 'w') as f:
            f.write(web_script)
        os.chmod('fixed_web_runner.sh', 0o755)
        logger.info("Скрипт запуска стабильного веб-сервера создан: fixed_web_runner.sh")
    except Exception as e:
        logger.error(f"Ошибка при создании скриптов запуска: {e}")
        raise

def main():
    """Основная функция настройки workflow"""
    try:
        logger.info("Начало настройки стабильного workflow...")
        
        # Создаем директорию для логов
        create_logs_directory()
        
        # Создаем скрипты запуска
        create_runner_scripts()
        
        # Создаем/перезапускаем workflow
        restart_workflow()
        
        logger.info("Настройка стабильного workflow завершена успешно")
        print("\n===== Настройка стабильного workflow =====")
        print("✅ Скрипты запуска созданы:")
        print("   - stable_bot_workflow.sh - для запуска только бота")
        print("   - fixed_web_runner.sh - для запуска веб-сервера с ботом")
        print("\n✅ Workflow 'stable_bot' настроен для запуска бота")
        print("\nДля запуска бота используйте:")
        print("./stable_bot_workflow.sh")
        print("\nДля запуска веб-сервера с ботом используйте:")
        print("./fixed_web_runner.sh")
        print("==========================================")
    except Exception as e:
        logger.error(f"Критическая ошибка при настройке workflow: {e}")
        print(f"❌ Ошибка при настройке workflow: {e}")

if __name__ == "__main__":
    main()
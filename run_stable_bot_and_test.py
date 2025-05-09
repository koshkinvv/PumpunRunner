#!/usr/bin/env python3
"""
Скрипт для запуска стабильного бота и проведения базовых тестов.
Выполняет следующие задачи:
1. Проверка конфигурации и окружения
2. Тестирование подключения к OpenAI API
3. Тестирование подключения к БД
4. Подготовка и запуск бота
"""
import os
import sys
import time
import json
import argparse
import logging
import subprocess
import psutil
import signal
from datetime import datetime

# Настройка логирования
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = f"{LOG_DIR}/bot_launch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename)
    ]
)
logger = logging.getLogger("bot_launcher")

def check_environment():
    """Проверяет наличие необходимых переменных окружения и конфигураций"""
    logger.info("Проверка окружения и конфигурации...")
    
    required_env_vars = ["TELEGRAM_TOKEN", "OPENAI_API_KEY", "DATABASE_URL"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Отсутствуют необходимые переменные окружения: {', '.join(missing_vars)}")
        return False
    
    # Проверка наличия ключевых файлов
    required_files = ["run_fixed_bot.py", "bot_modified.py", "models.py", "db_manager.py"]
    missing_files = [file for file in required_files if not os.path.exists(file)]
    
    if missing_files:
        logger.error(f"Отсутствуют необходимые файлы: {', '.join(missing_files)}")
        return False
    
    logger.info("✅ Проверка окружения и конфигурации успешно завершена")
    return True

def test_openai_api():
    """Тестирует подключение к OpenAI API"""
    logger.info("Тестирование подключения к OpenAI API...")
    
    try:
        output = subprocess.check_output(["python", "openai_test.py"], text=True)
        if "ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО" in output:
            logger.info("✅ Тестирование OpenAI API завершено успешно")
            return True
        else:
            logger.error("❌ Тестирование OpenAI API завершилось с ошибками")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании OpenAI API: {e}")
        return False

def test_database():
    """Тестирует подключение к базе данных"""
    logger.info("Тестирование подключения к базе данных...")
    
    try:
        # Простая проверка через psql
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.error("❌ Не указан DATABASE_URL")
            return False
            
        # Простая проверка активности соединения с БД
        test_query = "SELECT 1 AS test;"
        cmd = f"psql {db_url} -c \"{test_query}\" -t"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"❌ Ошибка подключения к БД: {result.stderr}")
            return False
        
        logger.info("✅ Успешное подключение к базе данных")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании базы данных: {e}")
        return False

def terminate_all_bot_processes():
    """Завершает все запущенные процессы бота"""
    logger.info("Поиск и завершение всех запущенных процессов бота...")
    
    current_pid = os.getpid()
    terminated_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Пропускаем текущий процесс
            if proc.pid == current_pid:
                continue
                
            # Проверяем командную строку процесса
            if proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if 'python' in cmdline and ('bot.py' in cmdline or 'bot_modified.py' in cmdline or 'run_' in cmdline):
                    logger.info(f"Завершение процесса бота: {proc.pid}, {cmdline}")
                    os.kill(proc.pid, signal.SIGTERM)
                    terminated_count += 1
                    
                    # Короткая пауза для корректного завершения
                    time.sleep(0.5)
                    
                    # Убиваем процесс если он все еще работает
                    if psutil.pid_exists(proc.pid):
                        logger.warning(f"Процесс {proc.pid} не завершился по SIGTERM, отправляем SIGKILL")
                        os.kill(proc.pid, signal.SIGKILL)
        except Exception:
            pass
    
    logger.info(f"Завершено {terminated_count} процессов бота")
    
    # Проверка, что процессы действительно завершены
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if 'python' in cmdline and ('bot.py' in cmdline or 'bot_modified.py' in cmdline):
                    logger.warning(f"Процесс бота все еще работает: {proc.pid}, {cmdline}")
                    return False
        except Exception:
            pass
    
    logger.info("✅ Все процессы бота успешно завершены")
    return True

def launch_bot(mode="bot"):
    """Запускает бота в выбранном режиме"""
    logger.info(f"Запуск бота в режиме: {mode}")
    
    # Сначала завершаем все запущенные процессы бота
    terminate_all_bot_processes()
    
    # Запускаем бота в выбранном режиме
    try:
        if mode == "bot":
            # Только бот через стабильный скрипт
            subprocess.Popen(["./stable_bot_workflow.sh"])
            logger.info("✅ Бот запущен в режиме 'только бот'")
        elif mode == "web":
            # Бот + веб-сервер
            subprocess.Popen(["./fixed_web_runner.sh"])
            logger.info("✅ Бот запущен в режиме 'бот + веб-сервер'")
        else:
            logger.error(f"❌ Неизвестный режим запуска: {mode}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        return False

def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="Запуск стабильного бота и проведение тестов")
    parser.add_argument("--mode", choices=["bot", "web"], default="bot", 
                      help="Режим запуска: 'bot' - только бот, 'web' - бот + веб-сервер")
    parser.add_argument("--skip-tests", action="store_true", 
                      help="Пропустить тесты и сразу запустить бота")
    args = parser.parse_args()
    
    print(f"{'='*50}")
    print(f"ЗАПУСК СТАБИЛЬНОГО БОТА И ТЕСТИРОВАНИЕ")
    print(f"{'='*50}")
    
    # Проверяем окружение
    env_check = check_environment()
    if not env_check:
        logger.error("Проверка окружения не пройдена, отмена запуска")
        sys.exit(1)
    
    # Проводим тесты, если не указано пропустить их
    if not args.skip_tests:
        # Тестируем OpenAI API
        api_test = test_openai_api()
        if not api_test:
            logger.warning("Тест OpenAI API не пройден, но продолжаем запуск")
        
        # Тестируем базу данных
        db_test = test_database()
        if not db_test:
            logger.warning("Тест базы данных не пройден, но продолжаем запуск")
    else:
        logger.info("Тесты пропущены по запросу")
    
    # Запускаем бота
    launch_success = launch_bot(mode=args.mode)
    
    if launch_success:
        print(f"\n{'='*50}")
        print(f"БОТ УСПЕШНО ЗАПУЩЕН В РЕЖИМЕ '{args.mode.upper()}'")
        print(f"{'='*50}")
        logger.info(f"Бот успешно запущен в режиме '{args.mode}'")
    else:
        print(f"\n{'='*50}")
        print(f"ОШИБКА ПРИ ЗАПУСКЕ БОТА")
        print(f"{'='*50}")
        logger.error("Не удалось запустить бота")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Завершение работы по запросу пользователя")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
#!/usr/bin/env python
"""
Скрипт для запуска только одного экземпляра бота.
Завершает все существующие экземпляры и запускает новый с контролем конфликтов.
"""

import os
import sys
import time
import signal
import subprocess
import logging
import psutil
import json
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/single_bot_launcher.log")
    ]
)

logger = logging.getLogger('single_bot_launcher')

def kill_all_bot_processes():
    """Завершает все запущенные процессы бота и связанные с ним процессы."""
    logger.info("Завершение всех запущенных экземпляров бота...")
    
    # Список ключевых слов для поиска процессов бота
    bot_keywords = ["main.py", "bot_monitor.py", "deploy_bot.py", "bot_runner"]
    skip_keywords = ["start_single_bot.py"]  # Пропускаем текущий скрипт
    
    # Получаем PID текущего процесса
    current_pid = os.getpid()
    
    # Количество найденных и завершенных процессов
    found_procs = 0
    terminated_procs = 0
    
    # Собираем все PID процессов для завершения
    pids_to_kill = []
    
    # Первый проход: находим все процессы для завершения
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Пропускаем текущий процесс
            if proc.info['pid'] == current_pid:
                continue
                
            # Проверяем командную строку
            cmdline = ' '.join(proc.info['cmdline'] or [])
            
            # Пропускаем процессы из списка исключений
            if any(keyword in cmdline for keyword in skip_keywords):
                continue
                
            # Ищем процессы по ключевым словам
            if any(keyword in cmdline for keyword in bot_keywords) or 'deploy_bot.py' in cmdline:
                logger.info(f"Найден процесс бота: PID {proc.info['pid']}, CMD: {cmdline[:50]}...")
                pids_to_kill.append(proc.info['pid'])
                found_procs += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception) as e:
            logger.error(f"Ошибка при проверке процесса: {e}")
    
    logger.info(f"Всего найдено процессов для завершения: {found_procs}")
    
    # Второй проход: завершаем все найденные процессы
    for pid in pids_to_kill:
        try:
            if psutil.pid_exists(pid):
                logger.info(f"Завершение процесса {pid}...")
                try:
                    # Сначала пробуем мягкое завершение
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)  # Даем процессу время на завершение
                    
                    # Если процесс все еще работает, используем SIGKILL
                    if psutil.pid_exists(pid):
                        logger.warning(f"Процесс {pid} не завершился мягко. Применяем SIGKILL.")
                        os.kill(pid, signal.SIGKILL)
                        time.sleep(0.5)
                    
                    # Проверяем, завершился ли процесс
                    if not psutil.pid_exists(pid):
                        logger.info(f"Процесс {pid} успешно завершен")
                        terminated_procs += 1
                    else:
                        logger.error(f"Не удалось завершить процесс {pid}")
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса {pid}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при проверке существования процесса {pid}: {e}")
    
    logger.info(f"Успешно завершено процессов: {terminated_procs} из {found_procs}")
    
    # Дополнительная проверка на наличие "зомби" процессов
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if proc.info['pid'] != current_pid and any(keyword in cmdline for keyword in bot_keywords):
                logger.warning(f"После завершения все еще работает процесс: PID {proc.info['pid']}, CMD: {cmdline[:50]}...")
        except:
            pass
    
    return terminated_procs

def reset_telegram_api_session():
    """Сбрасывает сессию Telegram API для предотвращения конфликтов."""
    logger.info("Сброс сессии Telegram API...")
    token = os.environ.get('TELEGRAM_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
    
    # Удаляем вебхук
    try:
        webhook_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(webhook_url)
        logger.info(f"Удаление вебхука: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # Делаем несколько попыток сброса сессии
    success = False
    for attempt in range(5):
        try:
            # Используем разные значения таймаута
            timeout = 3 + attempt
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-1&limit=1&timeout={timeout}"
            response = requests.get(url)
            
            logger.info(f"Попытка сброса #{attempt+1}: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info(f"Успешный сброс API: {json.dumps(data)}")
                    success = True
                else:
                    error = data.get("description", "Unknown error")
                    logger.warning(f"Ошибка при сбросе API: {error}")
                    
                    # Если ошибка связана с конфликтом, увеличиваем время ожидания
                    if "Conflict" in error:
                        wait_time = 5 + attempt * 3
                        logger.info(f"Конфликт API. Ждем {wait_time} секунд...")
                        time.sleep(wait_time)
            else:
                logger.warning(f"Неуспешный статус ответа: {response.status_code}")
                
            # Пауза между попытками
            time.sleep(2 + attempt)
        except Exception as e:
            logger.error(f"Ошибка при попытке сброса #{attempt+1}: {e}")
            time.sleep(2)
    
    # Финальная задержка перед запуском
    if success:
        logger.info("Сессия Telegram API успешно сброшена")
    else:
        logger.warning("Не удалось полностью сбросить сессию API")
    
    # В любом случае, ждем еще немного, чтобы Telegram API освободил ресурсы
    time.sleep(10)
    
    return success

def launch_bot():
    """Запускает основной скрипт main.py с контролем его выполнения."""
    logger.info("Запуск бота...")
    
    # Создаем директорию для логов, если её нет
    os.makedirs("logs", exist_ok=True)
    
    # Запускаем скрипт main.py напрямую
    try:
        process = subprocess.Popen(
            ["python", "main.py"],
            stdout=open("logs/bot_output_new.log", "a"),
            stderr=open("logs/bot_error_new.log", "a")
        )
        
        logger.info(f"Бот запущен с PID: {process.pid}")
        
        # Ждем 5 секунд, чтобы убедиться, что процесс не завершился сразу
        time.sleep(5)
        
        # Проверяем, что процесс все еще работает
        if psutil.pid_exists(process.pid):
            logger.info(f"Процесс бота {process.pid} успешно работает")
            return process.pid
        else:
            logger.error("Процесс бота завершился сразу после запуска")
            return None
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return None

def main():
    """Основная функция запуска бота в единственном экземпляре."""
    logger.info("=" * 50)
    logger.info("Запуск бота в единственном экземпляре")
    logger.info("=" * 50)
    
    # Шаг 1: Завершаем все существующие экземпляры бота
    killed = kill_all_bot_processes()
    logger.info(f"Завершено {killed} процессов бота")
    
    # Даем время на полное завершение всех процессов
    time.sleep(5)
    
    # Шаг 2: Сбрасываем сессию Telegram API
    reset_telegram_api_session()
    
    # Шаг 3: Запускаем бота
    bot_pid = launch_bot()
    
    if bot_pid:
        logger.info(f"Бот успешно запущен с PID {bot_pid}")
        
        # Ждем завершения процесса (чтобы скрипт не завершился)
        try:
            while psutil.pid_exists(bot_pid):
                logger.info(f"Бот (PID {bot_pid}) работает нормально")
                time.sleep(60)  # Проверяем каждую минуту
                
            logger.warning(f"Процесс бота (PID {bot_pid}) завершился!")
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания. Завершение работы...")
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
    else:
        logger.error("Не удалось запустить бота")

if __name__ == "__main__":
    main()
#!/usr/bin/env python
"""
Скрипт запуска бота для Replit Deployment.
Этот скрипт создан специально для работы в режиме Background Worker на Reserved VM.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import psutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('deploy_bot')

def kill_running_bots():
    """Убивает все запущенные процессы бота."""
    try:
        logger.info("Поиск и завершение запущенных экземпляров бота...")
        # Используем команды системы для поиска и устранения всех процессов бота
        try:
            # Пытаемся убить все процессы python, связанные с ботом
            os.system("pkill -f 'python.*main.py'")
            os.system("pkill -f 'python.*bot_monitor.py'")
            time.sleep(2)
        except:
            pass
            
        # Также ищем через psutil для более надежного завершения
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Ищем все процессы main.py или bot_monitor.py, но исключаем текущий скрипт
                if proc.info['cmdline'] and proc.info['pid'] != os.getpid():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if any(pattern in cmdline for pattern in ['main.py', 'bot_monitor.py']):
                        logger.info(f"Убиваем процесс: {proc.info['pid']} - {cmdline}")
                        try:
                            os.kill(proc.info['pid'], signal.SIGTERM)
                            time.sleep(1)
                            
                            # Проверяем, завершился ли процесс
                            if psutil.pid_exists(proc.info['pid']):
                                os.kill(proc.info['pid'], signal.SIGKILL)
                        except:
                            logger.warning(f"Не удалось завершить процесс {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception) as err:
                logger.warning(f"Ошибка при проверке процесса: {err}")
    except Exception as e:
        logger.error(f"Ошибка при убийстве процессов бота: {e}")

def start_bot_and_monitor():
    """Запускает бота и монитор здоровья."""
    try:
        # Сначала убиваем любые запущенные экземпляры бота
        kill_running_bots()
        
        # Создаем директорию для логов, если её нет
        os.makedirs("logs", exist_ok=True)
        
        # Запускаем бота
        logger.info("Запускаем бота...")
        bot_process = subprocess.Popen(
            ["python", "main.py"],
            stdout=open("logs/bot_output.log", "a"),
            stderr=open("logs/bot_error.log", "a")
        )
        
        # Запускаем монитор в отдельном процессе
        logger.info("Запускаем монитор здоровья...")
        monitor_process = subprocess.Popen(
            ["python", "bot_monitor.py"],
            stdout=open("logs/monitor_output.log", "a"),
            stderr=open("logs/monitor_error.log", "a")
        )
        
        logger.info(f"Бот (PID: {bot_process.pid}) и монитор здоровья (PID: {monitor_process.pid}) запущены")
        
        # Ждем некоторое время, чтобы убедиться, что процессы стартовали нормально
        time.sleep(5)
        
        # Проверяем, что оба процесса все еще работают
        bot_running = psutil.pid_exists(bot_process.pid)
        monitor_running = psutil.pid_exists(monitor_process.pid)
        
        if not bot_running or not monitor_running:
            logger.error(f"Не удалось запустить процессы: бот {'работает' if bot_running else 'не работает'}, "
                         f"монитор {'работает' if monitor_running else 'не работает'}")
            
            # Убиваем оставшиеся процессы
            for pid in [bot_process.pid, monitor_process.pid]:
                if psutil.pid_exists(pid):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except:
                        pass
            return False
        
        return bot_process, monitor_process
    except Exception as e:
        logger.error(f"Ошибка при запуске бота с монитором: {e}")
        return False

def monitor_bot_processes(bot_process, monitor_process):
    """Мониторит процессы бота и монитора, перезапускает их при необходимости."""
    logger.info("Начинаем мониторинг процессов бота и монитора здоровья")
    
    while True:
        try:
            # Проверяем, работают ли процессы
            bot_running = psutil.pid_exists(bot_process.pid)
            monitor_running = psutil.pid_exists(monitor_process.pid)
            
            if not bot_running or not monitor_running:
                logger.warning(f"Обнаружена остановка процессов: бот {'работает' if bot_running else 'не работает'}, "
                             f"монитор {'работает' if monitor_running else 'не работает'}")
                
                # Перезапускаем процессы
                logger.info("Перезапускаем все процессы...")
                
                # Сначала убиваем оставшиеся процессы
                kill_running_bots()
                time.sleep(2)
                
                # Затем запускаем заново
                result = start_bot_and_monitor()
                if result:
                    bot_process, monitor_process = result
                    logger.info(f"Процессы успешно перезапущены: бот (PID: {bot_process.pid}), "
                               f"монитор (PID: {monitor_process.pid})")
                else:
                    logger.error("Не удалось перезапустить процессы")
            
            # Обновляем статус каждые 30 секунд
            logger.info(f"Процессы работают: бот (PID: {bot_process.pid}), монитор (PID: {monitor_process.pid})")
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        
        # Ждем 30 секунд перед следующей проверкой
        time.sleep(30)

def reset_telegram_api_session():
    """
    Сбрасывает текущую сессию Telegram API для предотвращения конфликтов.
    Удаляет вебхуки и делает несколько попыток сброса offset.
    """
    try:
        token = os.environ.get('TELEGRAM_TOKEN')
        if not token:
            logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
            return False
            
        logger.info("Начинаем сброс сессии Telegram API...")
        
        # Проверяем статус вебхука
        webhook_info = os.popen(f"curl -s https://api.telegram.org/bot{token}/getWebhookInfo").read()
        logger.info(f"Webhook info: {webhook_info}")
        
        # Пытаемся удалить вебхук
        delete_result = os.popen(f"curl -s https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true").read()
        logger.info(f"Delete webhook result: {delete_result}")
        
        # Делаем несколько попыток сбросить сессию getUpdates с разными параметрами
        success = False
        for attempt in range(5):
            try:
                # Сброс с разными таймаутами и лимитами
                reset_result = os.popen(f"curl -s 'https://api.telegram.org/bot{token}/getUpdates?offset=-1&limit=1&timeout={attempt+1}'").read()
                logger.info(f"Reset attempt {attempt+1}: {reset_result}")
                
                if '"ok":true' in reset_result:
                    success = True
                
                # Пауза между попытками увеличивается с каждым разом
                time.sleep(3 + attempt*2)
            except Exception as inner_err:
                logger.error(f"Ошибка при попытке сброса #{attempt+1}: {inner_err}")
        
        # Дополнительная финальная попытка с большим таймаутом
        if not success:
            reset_final = os.popen(f"curl -s 'https://api.telegram.org/bot{token}/getUpdates?offset=-1&limit=1&timeout=10'").read()
            logger.info(f"Final reset attempt: {reset_final}")
        
        # Даем API время на обработку наших запросов
        logger.info("Ожидание 10 секунд после сброса сессии API...")
        time.sleep(10)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при сбросе сессии Telegram API: {e}")
        return False

def main():
    """Основная функция для запуска и мониторинга бота в режиме фонового процесса."""
    logger.info("Запуск бота для Replit Deployment (Reserved VM Background Worker)")
    
    # Проверяем, есть ли токен в переменных окружения
    if not os.environ.get('TELEGRAM_TOKEN'):
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения! Бот не может быть запущен.")
        sys.exit(1)
    
    # Сбрасываем сессию Telegram API, чтобы избежать конфликтов
    reset_telegram_api_session()
    
    # Используем системные команды для более надежного завершения процессов
    logger.info("Завершаем все запущенные процессы бота...")
    os.system("pkill -9 -f 'python.*main.py'")
    os.system("pkill -9 -f 'python.*bot_monitor.py'")
    os.system("pkill -9 -f 'python.*deploy_bot.py' -o")  # Убиваем только старые экземпляры (-o)
    time.sleep(2)
    
    # Удаляем лок-файлы, если они остались от предыдущих запусков
    for lock_file in ['./uv.lock', './bot.lock', './telegram.lock', './instance.lock', './bot_lock.pid']:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info(f"Удален lock-файл: {lock_file}")
        except Exception as e:
            logger.error(f"Не удалось удалить lock-файл {lock_file}: {e}")
    
    # Записываем PID текущего процесса в файл для того, чтобы избежать 
    # запуска параллельных экземпляров в будущем
    try:
        with open('./bot_lock.pid', 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"Записан PID процесса в bot_lock.pid: {os.getpid()}")
    except Exception as e:
        logger.error(f"Не удалось записать PID в файл: {e}")
    
    # Ждем 15 секунд перед запуском для того, чтобы убедиться, что все старые процессы завершены
    # и чтобы Telegram API успел сбросить предыдущую сессию
    logger.info("Ожидание 15 секунд перед запуском...")
    time.sleep(15)
    
    # Запускаем бота и монитор
    result = start_bot_and_monitor()
    if result:
        bot_process, monitor_process = result
        logger.info("Бот и монитор здоровья успешно запущены")
        
        # Начинаем мониторинг процессов и держим скрипт запущенным
        monitor_bot_processes(bot_process, monitor_process)
    else:
        logger.error("Не удалось запустить бота с монитором")
        sys.exit(1)

if __name__ == "__main__":
    main()
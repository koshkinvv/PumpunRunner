"""
Скрипт мониторинга здоровья для бота. Проверяет, запущен ли бот, и перезапускает его при необходимости.
"""
import os
import time
import subprocess
import signal
import logging
import psutil
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_monitor.log"),
        logging.StreamHandler()
    ]
)

# Путь к основному скрипту бота
BOT_SCRIPT = "main.py"
# Интервал проверки в секундах
CHECK_INTERVAL = 300  # 5 минут

def is_bot_running():
    """Проверяет, запущен ли бот"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Ищем процесс Python, выполняющий main.py
            if 'python' in proc.info['name'].lower() and any(BOT_SCRIPT in cmd for cmd in proc.info['cmdline'] if cmd):
                # Проверяем, что процесс не зомби и отвечает
                if proc.status() != psutil.STATUS_ZOMBIE:
                    return True, proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False, None

def start_bot():
    """Запускает бота"""
    logging.info("Запуск бота...")
    try:
        # Запускаем бота в фоновом режиме
        process = subprocess.Popen(["python", BOT_SCRIPT], 
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  start_new_session=True)
        logging.info(f"Бот запущен с PID {process.pid}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        return False

def stop_bot(pid):
    """Останавливает бота"""
    if not pid:
        return
    
    logging.info(f"Останавливаем бота с PID {pid}...")
    try:
        os.kill(pid, signal.SIGTERM)
        # Даем процессу время на корректное завершение
        time.sleep(5)
        # Проверяем, завершился ли процесс
        if psutil.pid_exists(pid):
            logging.warning(f"Бот с PID {pid} не завершился корректно, применяем SIGKILL")
            os.kill(pid, signal.SIGKILL)
    except Exception as e:
        logging.error(f"Ошибка при остановке бота: {e}")

def check_and_restart():
    """Проверяет состояние бота и перезапускает при необходимости"""
    running, pid = is_bot_running()
    
    if not running:
        logging.warning("Бот не запущен, запускаем...")
        start_bot()
    else:
        logging.info(f"Бот работает (PID: {pid})")
        
        # Проверка, не завис ли бот (можно добавить дополнительные проверки)
        try:
            proc = psutil.Process(pid)
            # Если CPU использование 0% в течение длительного времени, возможно бот завис
            if proc.cpu_percent(interval=1.0) == 0.0:
                logging.warning(f"Бот может быть завис (PID: {pid}), перезапускаем...")
                stop_bot(pid)
                start_bot()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logging.warning("Не удалось проверить состояние бота, пробуем перезапустить...")
            stop_bot(pid)
            start_bot()

def main():
    """Основная функция мониторинга"""
    logging.info("Запуск системы мониторинга бота")
    
    try:
        # Первичная проверка
        running, pid = is_bot_running()
        if running:
            logging.info(f"Бот уже запущен (PID: {pid})")
        else:
            logging.info("Бот не запущен, запускаем...")
            start_bot()
        
        # Основной цикл мониторинга
        while True:
            try:
                check_and_restart()
            except Exception as e:
                logging.error(f"Ошибка в цикле мониторинга: {e}")
            
            # Логируем время следующей проверки
            next_check = datetime.now().timestamp() + CHECK_INTERVAL
            logging.info(f"Следующая проверка: {datetime.fromtimestamp(next_check).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Ждем до следующей проверки
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        logging.info("Мониторинг остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка в системе мониторинга: {e}")
    finally:
        logging.info("Система мониторинга завершает работу")

if __name__ == "__main__":
    main()
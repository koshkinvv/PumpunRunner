
import logging
import sys
import time
import os
import traceback
import signal
import psutil
import fcntl
import datetime
import asyncio
import threading
from bot_modified import setup_bot
from app import app  # Импортируем Flask-приложение из app.py
from training_reminder import schedule_reminders

# Константы для мониторинга здоровья
HEALTH_CHECK_FILE = "bot_health.txt"
LOCK_FILE = "/tmp/telegram_bot.lock"
BOT_PROCESS_NAME = "main.py"

# Настройка логирования в файл и консоль
def setup_logging():
    """Настраивает расширенное логирование для бота."""
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    log_file = os.path.join(log_directory, "bot.log")
    
    # Настройка логирования
    handlers = [
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Дополнительное логирование для отслеживания необработанных исключений
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Если это KeyboardInterrupt (Ctrl+C), передаем управление стандартному обработчику
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logging.error("Необработанное исключение:", 
                     exc_info=(exc_type, exc_value, exc_traceback))
    
    # Устанавливаем обработчик необработанных исключений
    sys.excepthook = handle_exception

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        with open(HEALTH_CHECK_FILE, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        logging.error(f"Ошибка при обновлении файла проверки здоровья: {e}")

def check_and_kill_other_instances():
    """Проверяет наличие других экземпляров бота и завершает их."""
    current_pid = os.getpid()
    
    try:
        # Ищем экземпляры бота с тем же именем скрипта
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.info['pid'] == current_pid:
                    continue
                
                # Проверяем, не является ли процесс экземпляром бота
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    logging.warning(f"Найден другой экземпляр бота (PID: {proc.info['pid']}), завершаем его")
                    
                    # Пытаемся мягко завершить процесс
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(2)  # Даем время на завершение
                    
                    # Если процесс все еще жив, применяем SIGKILL
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
                        logging.warning(f"Процесс {proc.info['pid']} принудительно завершен")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                logging.warning(f"Ошибка при проверке процесса: {e}")
    except Exception as e:
        logging.error(f"Ошибка при проверке других экземпляров: {e}")

def try_lock_file():
    """Пытается получить блокировку файла для предотвращения запуска нескольких экземпляров."""
    try:
        # Создаем файл блокировки, если он не существует
        lock_file_handle = open(LOCK_FILE, 'w')
        
        # Пытаемся получить эксклюзивную блокировку файла
        fcntl.lockf(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Если блокировка получена успешно, возвращаем дескриптор файла
        return lock_file_handle
    except IOError:
        # Не удалось получить блокировку - другой экземпляр уже запущен
        logging.error("Не удалось получить блокировку файла. Другой экземпляр бота уже запущен.")
        
        # Проверяем и убиваем другие экземпляры
        check_and_kill_other_instances()
        
        # Пробуем еще раз получить блокировку
        time.sleep(2)
        return try_lock_file()
    except Exception as e:
        logging.error(f"Неожиданная ошибка при получении блокировки: {e}")
        return None

def release_lock(lock_file_handle):
    """Освобождает блокировку файла."""
    if lock_file_handle:
        try:
            fcntl.lockf(lock_file_handle, fcntl.LOCK_UN)
            lock_file_handle.close()
            logging.info("Блокировка файла освобождена")
        except Exception as e:
            logging.error(f"Ошибка при освобождении блокировки: {e}")

def setup_health_update():
    """Настраивает регулярное обновление файла здоровья."""
    # Обновляем файл здоровья при запуске
    update_health_check()
    
    # Настраиваем сигнальный обработчик для обновления файла здоровья
    def health_signal_handler(signum, frame):
        update_health_check()
    
    # Регистрируем обработчик для сигнала SIGUSR1
    signal.signal(signal.SIGUSR1, health_signal_handler)
    
    # Запускаем процесс регулярного обновления файла здоровья
    def send_health_signal():
        """Функция для отправки сигнала SIGUSR1 себе."""
        while True:
            try:
                os.kill(os.getpid(), signal.SIGUSR1)
            except:
                pass
            time.sleep(30)  # Обновляем каждые 30 секунд
    
    # Запускаем функцию в отдельном потоке
    import threading
    health_thread = threading.Thread(target=send_health_signal, daemon=True)
    health_thread.start()

def start_reminder_loop():
    """Запускает планировщик напоминаний о тренировках."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        logging.info("Запуск планировщика напоминаний о тренировках...")
        loop.run_until_complete(schedule_reminders())
    except Exception as e:
        logging.error(f"Ошибка в планировщике напоминаний: {e}")
    finally:
        loop.close()

def main():
    """Main function to start the Telegram bot."""
    # Setup logging
    setup_logging()
    
    logging.info("Вызываем run_one_bot.py для запуска единственного экземпляра бота...")
    try:
        # Импортируем функции из run_one_bot.py
        import run_one_bot
        
        # Останавливаем все запущенные экземпляры бота
        run_one_bot.kill_all_bot_processes()
        
        # Запускаем deploy_bot.py
        run_one_bot.run_deploy_bot()
        
        logging.info("Бот успешно запущен через run_one_bot.py")
        
        # Ждем, чтобы процесс main.py не завершился сразу
        while True:
            time.sleep(60)
            logging.info("main.py: мониторинг работы бота...")
            
    except Exception as e:
        logging.error(f"Ошибка при запуске через run_one_bot.py: {e}")
        logging.error(traceback.format_exc())
        
        # Если произошла ошибка при запуске через run_one_bot.py, 
        # пробуем запустить бота по старому методу
        logging.warning("Пробуем запустить бота по старому методу...")
        
        # Пытаемся получить блокировку файла
        lock_file_handle = try_lock_file()
        if not lock_file_handle:
            logging.critical("Не удалось получить блокировку файла после нескольких попыток. Выход.")
            return
        
        # Настраиваем обновление файла здоровья
        setup_health_update()
        
        try:
            # Проверяем и убиваем другие экземпляры бота
            check_and_kill_other_instances()
            
            # Запускаем планировщик напоминаний в отдельном потоке
            reminder_thread = threading.Thread(target=start_reminder_loop, daemon=True)
            reminder_thread.start()
            logging.info("Планировщик напоминаний о тренировках запущен в отдельном потоке")
            
            max_retries = 5
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Get the bot application
                    application = setup_bot()
                    
                    # Log startup message
                    logging.info("Runner profile bot started successfully!")
                    
                    # Run the bot until the user sends a signal to stop it
                    application.run_polling(drop_pending_updates=True)  # Игнорируем накопившиеся обновления
                    
                    # Если мы дошли сюда, значит бот завершился нормально
                    break
                    
                except Exception as e:
                    retry_count += 1
                    logging.error(f"Ошибка в работе бота (попытка {retry_count}/{max_retries}): {e}")
                    logging.error(traceback.format_exc())
                    
                    # Обновляем файл здоровья перед ожиданием
                    update_health_check()
                    
                    if retry_count < max_retries:
                        # Ждем перед повторной попыткой, увеличивая время ожидания с каждой попыткой
                        wait_time = 10 * retry_count
                        logging.info(f"Перезапуск бота через {wait_time} секунд...")
                        time.sleep(wait_time)
                    else:
                        logging.critical("Превышено максимальное количество попыток перезапуска. Бот остановлен.")
        finally:
            # Освобождаем блокировку файла перед выходом
            release_lock(lock_file_handle)

if __name__ == '__main__':
    main()

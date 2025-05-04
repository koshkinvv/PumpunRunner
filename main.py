
import logging
import sys
import time
import os
import traceback
import signal
import psutil
import fcntl
import datetime
from bot_modified import setup_bot
from app import app  # Импортируем Flask-приложение из app.py

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
                # Также добавляем прямое обновление файла здоровья для надежности
                update_health_check()
            except Exception as e:
                logging.error(f"Ошибка в процессе обновления здоровья: {e}")
            time.sleep(60)  # Увеличиваем интервал до 60 секунд для снижения нагрузки
    
    # Запускаем функцию в отдельном потоке
    import threading
    health_thread = threading.Thread(target=send_health_signal, daemon=True)
    health_thread.start()

def main():
    """Main function to start the Telegram bot."""
    # Setup logging
    setup_logging()
    
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
        
        max_retries = 10  # Увеличиваем количество попыток
        retry_count = 0
        
        # Логирование версии Python и системной информации
        logging.info(f"Python version: {sys.version}")
        
        # Логирование информации о системной памяти
        vm = psutil.virtual_memory()
        logging.info(f"System memory: total={vm.total/(1024*1024):.1f}MB, available={vm.available/(1024*1024):.1f}MB, percent={vm.percent}%")
        
        while retry_count < max_retries:
            try:
                # Обновляем файл здоровья перед каждой попыткой запуска
                update_health_check()
                
                # Get the bot application
                application = setup_bot()
                
                # Log startup message
                logging.info("Runner profile bot started successfully!")
                
                # Настраиваем обработчики сигналов для корректного завершения
                def signal_handler(signum, frame):
                    logging.info(f"Получен сигнал {signum}, завершаем работу бота")
                    application.stop()
                
                # Регистрируем обработчики сигналов
                signal.signal(signal.SIGTERM, signal_handler)
                signal.signal(signal.SIGINT, signal_handler)
                
                # Run the bot until the user sends a signal to stop it
                application.run_polling(
                    drop_pending_updates=True,  # Игнорируем накопившиеся обновления
                    timeout=30,  # Увеличиваем timeout для долгих соединений
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
                
                # Если мы дошли сюда, значит бот завершился нормально
                logging.info("Бот завершился нормально")
                break
                
            except Exception as e:
                retry_count += 1
                logging.error(f"Ошибка в работе бота (попытка {retry_count}/{max_retries}): {e}")
                logging.error(traceback.format_exc())
                
                # Логирование состояния памяти при ошибке
                try:
                    process = psutil.Process(os.getpid())
                    mem_info = process.memory_info()
                    logging.warning(f"Memory usage: RSS={mem_info.rss/(1024*1024):.1f}MB, VMS={mem_info.vms/(1024*1024):.1f}MB")
                except Exception as mem_e:
                    logging.error(f"Не удалось получить информацию о памяти: {mem_e}")
                
                # Обновляем файл здоровья перед ожиданием
                update_health_check()
                
                if retry_count < max_retries:
                    # Используем экспоненциальную задержку для более эффективного восстановления
                    wait_time = min(60, 5 * (2 ** retry_count))  # Максимум 60 секунд
                    logging.info(f"Перезапуск бота через {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    logging.critical("Превышено максимальное количество попыток перезапуска. Бот остановлен.")
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    finally:
        # Завершающее логирование
        logging.info("Завершение работы бота")
        
        # Освобождаем блокировку файла перед выходом
        release_lock(lock_file_handle)

if __name__ == '__main__':
    main()

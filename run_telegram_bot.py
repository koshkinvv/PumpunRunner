#!/usr/bin/env python
"""
Скрипт для запуска Telegram бота с проверкой запущенных экземпляров.
Этот файл запускает только сам бот, проверяя наличие и удаляя дубликаты процессов.
"""

import sys
import os
import logging
import traceback
import importlib
import time
import signal
import psutil
import fcntl
import datetime

# Настройка логирования в файл и консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot_launcher.log")
    ]
)

logger = logging.getLogger("telegram_bot_launcher")

# Константы
LOCK_FILE = "/tmp/telegram_bot_runner.lock"
HEALTH_FILE = "bot_health.txt"

def check_and_kill_other_instances():
    """Проверяет и завершает все другие экземпляры бота."""
    current_pid = os.getpid()
    logger.info(f"Текущий PID: {current_pid}")
    
    # Список ключевых слов для поиска процессов бота
    bot_keywords = [
        "bot_modified.py",
        "run_telegram_bot.py",
        "python.*telegram",
        "getUpdates",
        "start_bot_with_monitor.py"
    ]
    
    killed_processes = 0
    
    # Ищем процессы по ключевым словам
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.info['pid'] == current_pid:
                    continue
                    
                # Проверяем командную строку процесса
                if proc.info['cmdline']:
                    cmd_line = " ".join(proc.info['cmdline'])
                    
                    # Проверяем, содержит ли командная строка ключевые слова
                    is_bot_process = any(keyword in cmd_line for keyword in bot_keywords)
                    
                    if is_bot_process:
                        logger.warning(f"Найден другой процесс бота (PID: {proc.info['pid']}), завершаем его")
                        try:
                            # Пытаемся мягко завершить процесс
                            process = psutil.Process(proc.info['pid'])
                            process.terminate()
                            
                            # Даем процессу время на завершение
                            gone, alive = psutil.wait_procs([process], timeout=3)
                            
                            if alive:
                                # Если процесс не завершился, применяем SIGKILL
                                logger.warning(f"Процесс {proc.info['pid']} не отвечает, принудительно завершаем")
                                process.kill()
                                
                            killed_processes += 1
                        except psutil.NoSuchProcess:
                            # Процесс уже завершен
                            pass
                        except Exception as e:
                            logger.error(f"Ошибка при завершении процесса {proc.info['pid']}: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                # Процесс мог завершиться между итерациями или нет доступа
                continue
            except Exception as e:
                logger.error(f"Ошибка при проверке процесса: {e}")
                
        # Дополнительная проверка с помощью bash команд
        os.system("pkill -f 'python.*bot_modified.py'")
        os.system("pkill -f 'python.*getUpdates'")
        
        logger.info(f"Завершено {killed_processes} других экземпляров бота")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке запущенных экземпляров: {e}")

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
        logger.error("Не удалось получить блокировку файла. Другой экземпляр бота уже запущен.")
        
        # Проверяем и завершаем другие экземпляры
        check_and_kill_other_instances()
        
        # Пробуем еще раз получить блокировку
        time.sleep(2)
        return try_lock_file()
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении блокировки: {e}")
        return None

def release_lock(lock_file_handle):
    """Освобождает блокировку файла."""
    if lock_file_handle:
        try:
            fcntl.lockf(lock_file_handle, fcntl.LOCK_UN)
            lock_file_handle.close()
            logger.info("Блокировка файла освобождена")
        except Exception as e:
            logger.error(f"Ошибка при освобождении блокировки: {e}")

def update_health_file():
    """Обновляет файл здоровья бота."""
    try:
        with open(HEALTH_FILE, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла здоровья: {e}")

def setup_health_update():
    """Настраивает периодическое обновление файла здоровья."""
    import threading
    
    def health_updater():
        """Периодически обновляет файл здоровья."""
        while True:
            try:
                update_health_file()
            except Exception as e:
                logger.error(f"Ошибка в обновлении здоровья: {e}")
            time.sleep(60)  # Обновляем каждую минуту
    
    # Запускаем обновление в отдельном потоке
    thread = threading.Thread(target=health_updater, daemon=True)
    thread.start()
    
    return thread

def setup_memory_monitor():
    """Настраивает мониторинг памяти."""
    import threading
    
    def memory_monitor():
        """Мониторит использование памяти процессом."""
        last_check = time.time()
        last_rss = 0
        
        while True:
            try:
                current_time = time.time()
                
                # Проверяем каждые 5 минут
                if current_time - last_check >= 300:
                    process = psutil.Process(os.getpid())
                    current_rss = process.memory_info().rss
                    
                    # Логируем использование памяти
                    vm = psutil.virtual_memory()
                    logger.info(f"Использование памяти: "
                              f"Процесс: {current_rss/(1024*1024):.1f}MB, "
                              f"Система: доступно {vm.available/(1024*1024):.1f}MB из {vm.total/(1024*1024):.1f}MB ({vm.percent}%)")
                    
                    # Проверка на резкий рост памяти
                    if last_rss > 0:
                        percentage_increase = (current_rss - last_rss) / last_rss * 100
                        if percentage_increase > 25:  # Рост более чем на 25%
                            logger.warning(f"Обнаружен значительный рост памяти: {percentage_increase:.1f}%")
                            
                            # Если рост очень большой, рекомендуем перезапуск
                            if percentage_increase > 100:  # Рост более чем вдвое
                                logger.error("Критический рост памяти! Рекомендуется перезапуск бота.")
                    
                    # Обновляем значения для следующей проверки
                    last_rss = current_rss
                    last_check = current_time
            except Exception as e:
                logger.error(f"Ошибка в мониторинге памяти: {e}")
                
            time.sleep(60)  # Проверяем каждую минуту
    
    # Запускаем мониторинг в отдельном потоке
    thread = threading.Thread(target=memory_monitor, daemon=True)
    thread.start()
    
    return thread

def clean_old_logs():
    """Очищает старые файлы логов."""
    try:
        # Создаем директорию для логов, если она не существует
        os.makedirs("logs", exist_ok=True)
        
        # Получаем список всех файлов логов
        log_files = [f for f in os.listdir("logs") if f.endswith(".log")]
        
        # Если файлов меньше 10, ничего не делаем
        if len(log_files) < 10:
            return
            
        # Получаем информацию о времени создания файлов
        log_files_with_time = []
        for log_file in log_files:
            file_path = os.path.join("logs", log_file)
            creation_time = os.path.getctime(file_path)
            log_files_with_time.append((file_path, creation_time))
            
        # Сортируем файлы по времени создания (от старых к новым)
        log_files_with_time.sort(key=lambda x: x[1])
        
        # Удаляем самые старые файлы, оставляя только 10 последних
        files_to_delete = log_files_with_time[:-10]
        for file_path, _ in files_to_delete:
            try:
                os.remove(file_path)
                logger.info(f"Удален старый лог: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении лога {file_path}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при очистке старых логов: {e}")

def main():
    """Основная функция для запуска бота."""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)
    
    # Очищаем старые логи
    clean_old_logs()
    
    # Проверяем и завершаем все другие экземпляры бота
    check_and_kill_other_instances()
    
    # Пытаемся получить блокировку файла
    lock_file_handle = try_lock_file()
    if not lock_file_handle:
        logger.critical("Не удалось получить блокировку файла. Выход.")
        return
    
    # Настраиваем обновление файла здоровья
    health_thread = setup_health_update()
    
    # Настраиваем мониторинг памяти
    memory_thread = setup_memory_monitor()
    
    # Обработчик сигналов
    def signal_handler(sig, frame):
        logger.info(f"Получен сигнал {sig}, завершаем работу")
        release_lock(lock_file_handle)
        sys.exit(0)
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Запуск Telegram бота...")
    
    try:
        # Импортируем setup_bot из bot_modified.py
        from bot_modified import setup_bot
        
        # Получаем экземпляр приложения бота
        application = setup_bot()
        
        # Запускаем поллинг для получения обновлений
        logger.info("Запуск бота в режиме поллинга...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=None,
            close_loop=False,
            timeout=60
        )
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Освобождаем блокировку файла
        release_lock(lock_file_handle)
    
    logger.info("Завершение работы Telegram бота")

if __name__ == "__main__":
    main()
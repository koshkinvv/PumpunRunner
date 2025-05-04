import logging
import sys
import time
import os
import traceback
import signal
import psutil
import fcntl
import datetime
import threading
from bot_modified import setup_bot
from app import app  # Импортируем Flask-приложение из app.py

# Константы для мониторинга здоровья
HEALTH_CHECK_FILE = "bot_health.txt"
LOCK_FILE = "/tmp/telegram_bot.lock"
BOT_PROCESS_NAME = "main.py"

# Настройка логирования в файл и консоль
def setup_memory_monitoring():
    """Настраивает мониторинг памяти для выявления утечек."""
    memory_stats = {
        'last_check': time.time(),
        'last_rss': 0,
        'check_interval': 300,  # 5 минут между проверками
        'warning_threshold': 20  # 20% рост - порог для предупреждения
    }

    # Получаем начальное состояние памяти
    try:
        process = psutil.Process(os.getpid())
        memory_stats['last_rss'] = process.memory_info().rss
    except Exception as e:
        logging.error(f"Не удалось получить начальное состояние памяти: {e}")

    def check_memory_usage():
        """Периодически проверяет использование памяти для выявления утечек."""
        while True:
            try:
                current_time = time.time()
                # Проверяем каждые 5 минут
                if current_time - memory_stats['last_check'] >= memory_stats['check_interval']:
                    process = psutil.Process(os.getpid())
                    current_rss = process.memory_info().rss

                    # Вычисляем процент роста
                    if memory_stats['last_rss'] > 0:
                        percentage_increase = (current_rss - memory_stats['last_rss']) / memory_stats['last_rss'] * 100

                        # Если рост больше порога, логируем предупреждение
                        if percentage_increase > memory_stats['warning_threshold']:
                            logging.warning(f"Обнаружен существенный рост использования памяти: {percentage_increase:.1f}% "
                                          f"(с {memory_stats['last_rss']/(1024*1024):.1f}MB до {current_rss/(1024*1024):.1f}MB)")

                            # Получаем информацию о потоках
                            thread_count = threading.active_count()
                            logging.info(f"Активных потоков: {thread_count}")

                            # В случае очень сильного роста, можем запланировать перезапуск
                            if percentage_increase > 50:  # 50% рост
                                logging.warning("Значительный рост памяти. Возможно, есть утечка памяти.")

                    # Обновляем статистику
                    memory_stats['last_rss'] = current_rss
                    memory_stats['last_check'] = current_time

                    # Логируем текущее использование памяти
                    vm = psutil.virtual_memory()
                    logging.info(f"Мониторинг памяти: "
                               f"Процесс: {current_rss/(1024*1024):.1f}MB, "
                               f"Система: доступно {vm.available/(1024*1024):.1f}MB из {vm.total/(1024*1024):.1f}MB ({vm.percent}%)")
            except Exception as e:
                logging.error(f"Ошибка в мониторинге памяти: {e}")

            # Ждем 1 минуту перед следующей проверкой
            time.sleep(60)

    # Запускаем мониторинг в отдельном потоке
    memory_thread = threading.Thread(target=check_memory_usage, daemon=True)
    memory_thread.start()
    return memory_thread

def setup_network_monitoring():
    """Настраивает мониторинг сетевой активности."""
    def monitor_network():
        last_check = time.time()
        last_bytes_sent = 0
        last_bytes_recv = 0

        # Получаем начальные значения
        try:
            net_io = psutil.net_io_counters()
            last_bytes_sent = net_io.bytes_sent
            last_bytes_recv = net_io.bytes_recv
        except Exception as e:
            logging.error(f"Не удалось получить начальные значения сетевой активности: {e}")

        while True:
            try:
                time.sleep(60)  # Проверяем каждую минуту

                # Получаем текущие значения
                net_io = psutil.net_io_counters()
                current_time = time.time()
                time_diff = current_time - last_check

                # Вычисляем скорость передачи данных
                bytes_sent_diff = net_io.bytes_sent - last_bytes_sent
                bytes_recv_diff = net_io.bytes_recv - last_bytes_recv

                # Конвертируем в KB/s
                kb_sent_per_sec = bytes_sent_diff / time_diff / 1024
                kb_recv_per_sec = bytes_recv_diff / time_diff / 1024

                # Логируем значения каждые 5 минут или если обнаружена высокая активность
                if time_diff >= 300 or kb_sent_per_sec > 100 or kb_recv_per_sec > 100:
                    logging.info(f"Сетевая активность: Отправлено {kb_sent_per_sec:.1f} KB/s, Получено {kb_recv_per_sec:.1f} KB/s")
                    last_check = current_time
                    last_bytes_sent = net_io.bytes_sent
                    last_bytes_recv = net_io.bytes_recv
            except Exception as e:
                logging.error(f"Ошибка в мониторинге сети: {e}")

    # Запускаем мониторинг в отдельном потоке
    network_thread = threading.Thread(target=monitor_network, daemon=True)
    network_thread.start()
    return network_thread

def setup_logging():
    """Настраивает расширенное логирование для бота."""
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # Создаем ротируемый файл логов с временной меткой
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_directory, f"bot_{timestamp}.log")

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

        # Дополнительно логируем информацию о состоянии системы
        try:
            vm = psutil.virtual_memory()
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            logging.error(f"Состояние системы при исключении: "
                         f"RSS={mem_info.rss/(1024*1024):.1f}MB, "
                         f"Доступно {vm.available/(1024*1024):.1f}MB из {vm.total/(1024*1024):.1f}MB ({vm.percent}%)")

            # Также логируем информацию о потоках
            logging.error(f"Активных потоков: {threading.active_count()}")
        except Exception as e:
            logging.error(f"Не удалось получить информацию о системе: {e}")

    # Устанавливаем обработчик необработанных исключений
    sys.excepthook = handle_exception

    # Добавляем периодическое логирование общей информации о состоянии
    def log_system_state():
        while True:
            try:
                # Логируем информацию о системе каждые 10 минут
                vm = psutil.virtual_memory()
                process = psutil.Process(os.getpid())
                mem_info = process.memory_info()

                logging.info(f"Периодический отчет о состоянии: "
                           f"Процесс: {mem_info.rss/(1024*1024):.1f}MB, "
                           f"CPU: {process.cpu_percent()}%, "
                           f"Потоки: {threading.active_count()}, "
                           f"Система: доступно {vm.available/(1024*1024):.1f}MB из {vm.total/(1024*1024):.1f}MB ({vm.percent}%)")
            except Exception as e:
                logging.error(f"Ошибка при логировании состояния системы: {e}")

            # Ожидаем 10 минут
            time.sleep(600)

    # Запускаем периодическое логирование в отдельном потоке
    state_thread = threading.Thread(target=log_system_state, daemon=True)
    state_thread.start()

    # Запускаем мониторинг памяти
    setup_memory_monitoring()

    # Запускаем мониторинг сети
    setup_network_monitoring()

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

                # Проверка подключения к Telegram API перед запуском
                try:
                    logging.info("Проверка подключения к Telegram API...")
                    # Используем тестовый запрос для проверки соединения
                    async def check_connection():
                        await application.bot.get_me()
                    application.loop.run_until_complete(check_connection())
                    logging.info("Подключение к Telegram API успешно")
                except Exception as e:
                    logging.error(f"Ошибка подключения к Telegram API: {e}")
                    logging.error(traceback.format_exc())
                    raise  # Перезапустим бота через основной цикл retry

                # Настройка обработчика сетевых ошибок
                # Вызывается при возникновении сетевых проблем
                def network_error_handler(update, context):
                    logging.error(f"Ошибка сети при обработке обновления: {context.error}")
                    # Запись состояния памяти при сетевых ошибках
                    vm = psutil.virtual_memory()
                    logging.info(f"Состояние памяти: total={vm.total/(1024*1024):.1f}MB, available={vm.available/(1024*1024):.1f}MB, percent={vm.percent}%")
                    # Обновляем файл здоровья для предотвращения перезапуска
                    update_health_check()

                # Регистрируем обработчик ошибок
                application.add_error_handler(network_error_handler)

                # Run the bot until the user sends a signal to stop it
                # Используем только те параметры, которые поддерживаются текущей версией
                logging.info("Запускаем поллинг...")

                # Настраиваем таймауты для бота
                # Делаем это отдельно, т.к. некоторые параметры могут не поддерживаться в текущей версии
                try:
                    application.bot.defaults = {"timeout": 60}
                except Exception as e:
                    logging.warning(f"Не удалось установить таймаут для бота: {e}")

                # Запускаем бота с наиболее универсальными параметрами
                application.run_polling(
                    drop_pending_updates=True,  # Игнорируем накопившиеся обновления
                    allowed_updates=None,  # Принимаем все типы обновлений
                    close_loop=False,  # Не закрываем цикл событий после остановки
                    stop_signals=(signal.SIGINT, signal.SIGTERM),  # Сигналы для остановки
                    timeout=60  # Увеличиваем timeout для долгих соединений до 60 секунд
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
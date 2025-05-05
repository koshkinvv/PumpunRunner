#!/usr/bin/env python
"""
Скрипт для мониторинга состояния Telegram бота и его автоматического перезапуска.
"""

import os
import sys
import time
import signal
import psutil
import logging
import subprocess
import traceback
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('bot_monitor')

# Параметры мониторинга
BOT_PROCESS_NAME = "main.py"
CHECK_INTERVAL = 30  # секунд между проверками (уменьшаем для более быстрой реакции)
MAX_MEMORY_PERCENT = 80  # максимальный процент памяти (снижаем порог для более раннего обнаружения проблем)
RESTART_COOLDOWN = 120  # минимальное время между перезапусками (2 минуты - снижаем для более быстрого восстановления)
HEALTH_CHECK_FILE = "bot_health.txt"
HEALTH_CHECK_TIMEOUT = 120  # время в секундах, после которого считаем бот неактивным (уменьшаем для более быстрого обнаружения проблем)
MAX_CONSECUTIVE_RESTARTS = 3  # максимальное количество последовательных перезапусков за короткий период

last_restart_time = datetime.now() - timedelta(seconds=RESTART_COOLDOWN * 2)
consecutive_restarts = 0
restart_timestamps = []  # Храним время последних перезапусков

def kill_bot_processes():
    """Находит и завершает все процессы бота."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Проверяем командную строку на наличие имени скрипта бота
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    logger.info(f"Завершаем процесс бота: {proc.info['pid']}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)  # Даем процессу время на завершение
                    
                    # Если процесс все еще работает, принудительно завершаем
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Ошибка при завершении процессов бота: {e}")

def start_bot():
    """Запускает бот в новом процессе."""
    try:
        global last_restart_time, consecutive_restarts, restart_timestamps
        
        # Проверяем, не слишком ли много перезапусков подряд
        now = datetime.now()
        
        # Удаляем старые записи о перезапусках (старше 10 минут)
        restart_timestamps = [ts for ts in restart_timestamps if (now - ts).total_seconds() < 600]
        
        # Добавляем текущее время перезапуска
        restart_timestamps.append(now)
        
        # Если было слишком много перезапусков за короткий период
        if len(restart_timestamps) > MAX_CONSECUTIVE_RESTARTS:
            consecutive_restarts += 1
            logger.warning(f"Частые перезапуски бота: {len(restart_timestamps)} за последние 10 минут (всего последовательных: {consecutive_restarts})")
            
            # Если последовательных перезапусков слишком много, увеличиваем время ожидания перед следующим запуском
            if consecutive_restarts > 2:
                wait_time = min(300, 60 * consecutive_restarts)  # максимум 5 минут
                logger.warning(f"Увеличиваем время ожидания перед запуском: {wait_time} секунд")
                time.sleep(wait_time)
        else:
            consecutive_restarts = 0
        
        logger.info("Запускаем бота...")
        
        # Создаем директорию для логов, если она не существует
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        # Запускаем бота в фоновом режиме с перенаправлением вывода в файлы
        log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stdout_log = open(f"logs/bot_stdout_{log_timestamp}.log", "w")
        stderr_log = open(f"logs/bot_stderr_{log_timestamp}.log", "w")
        
        subprocess.Popen(
            ["python", "main.py"], 
            stdout=stdout_log,
            stderr=stderr_log,
            env=dict(os.environ),  # Передаем текущие переменные окружения
            cwd=os.getcwd()        # Запускаем бота в текущей директории
        )
        
        logger.info(f"Бот запущен, логи: stdout={stdout_log.name}, stderr={stderr_log.name}")
        
        # Обновляем время последнего перезапуска
        last_restart_time = now
        
        # Создаем файл проверки здоровья
        update_health_check()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        logger.error(traceback.format_exc())

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        with open(HEALTH_CHECK_FILE, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла проверки здоровья: {e}")

def check_bot_health():
    """Проверяет, что бот работает и отвечает."""
    try:
        # Проверяем, существует ли файл здоровья
        if not os.path.exists(HEALTH_CHECK_FILE):
            logger.warning("Файл проверки здоровья не найден")
            return False
        
        # Проверяем время последнего обновления
        with open(HEALTH_CHECK_FILE, "r") as f:
            health_time_str = f.read().strip()
        
        health_time = datetime.strptime(health_time_str, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()
        
        # Если файл не обновлялся слишком долго, считаем бот неактивным
        if (current_time - health_time).total_seconds() > HEALTH_CHECK_TIMEOUT:
            logger.warning(f"Последнее обновление здоровья: {health_time_str}, текущее время: {current_time}. Бот неактивен.")
            return False
        
        # Проверяем использование памяти
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_percent']):
            try:
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    if proc.info['memory_percent'] > MAX_MEMORY_PERCENT:
                        logger.warning(f"Бот использует слишком много памяти: {proc.info['memory_percent']}%")
                        return False
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Если все проверки прошли, бот здоров
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья бота: {e}")
        return False

def is_bot_running():
    """Проверяет, запущен ли бот."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке запуска бота: {e}")
        return False

def get_bot_memory_usage():
    """Возвращает информацию об использовании памяти ботом."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'memory_percent', 'cpu_percent']):
            try:
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    proc.cpu_percent()  # Первый вызов всегда возвращает 0, поэтому вызываем отдельно
                    time.sleep(0.1)
                    mem_info = proc.memory_info()
                    return {
                        'pid': proc.info['pid'],
                        'rss': mem_info.rss / (1024 * 1024),  # в МБ
                        'vms': mem_info.vms / (1024 * 1024),  # в МБ
                        'mem_percent': proc.memory_percent(),
                        'cpu_percent': proc.cpu_percent()
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о памяти: {e}")
        return None

def analyze_logs():
    """Анализирует логи бота для поиска ошибок."""
    try:
        # Проверяем, существует ли директория с логами
        if not os.path.exists("logs"):
            return
            
        # Находим последний файл с логами ошибок
        error_logs = [f for f in os.listdir("logs") if f.startswith("bot_stderr_")]
        if not error_logs:
            return
            
        # Сортируем по времени создания (самый новый последний)
        error_logs.sort()
        latest_error_log = os.path.join("logs", error_logs[-1])
        
        # Проверяем размер файла
        if os.path.getsize(latest_error_log) == 0:
            return
            
        # Читаем последние 20 строк файла
        with open(latest_error_log, "r") as f:
            lines = f.readlines()
            last_lines = lines[-20:] if len(lines) >= 20 else lines
            
        # Анализируем ошибки
        error_count = 0
        critical_errors = []
        
        for line in last_lines:
            if "ERROR" in line or "CRITICAL" in line or "Exception" in line or "Error" in line:
                error_count += 1
                critical_errors.append(line.strip())
                
        if error_count > 0:
            logger.warning(f"Обнаружено {error_count} ошибок в логах")
            for err in critical_errors[-3:]:  # Выводим только последние 3 ошибки
                logger.warning(f"Ошибка: {err}")
    except Exception as e:
        logger.error(f"Ошибка при анализе логов: {e}")

def check_and_restart_if_needed():
    """Проверяет состояние бота и перезапускает его при необходимости."""
    global last_restart_time
    
    # Анализируем логи для поиска ошибок
    analyze_logs()
    
    # Проверяем, не слишком ли часто перезапускается бот
    if (datetime.now() - last_restart_time).total_seconds() < RESTART_COOLDOWN:
        logger.info("Охлаждение перезапуска активно, пропускаем проверку")
        return
    
    # Если бот не запущен, запускаем его
    if not is_bot_running():
        logger.warning("Бот не запущен, запускаем")
        kill_bot_processes()  # На всякий случай убиваем все процессы
        start_bot()
        return
    
    # Получаем информацию об использовании ресурсов
    usage_info = get_bot_memory_usage()
    if usage_info:
        logger.info(f"Состояние бота (PID: {usage_info['pid']}): "
                   f"Память: {usage_info['rss']:.1f}MB ({usage_info['mem_percent']:.1f}%), "
                   f"CPU: {usage_info['cpu_percent']:.1f}%")
        
        # Проверяем использование CPU
        if usage_info['cpu_percent'] > 90:
            logger.warning(f"Высокая загрузка CPU: {usage_info['cpu_percent']:.1f}%")
    
    # Если бот запущен, проверяем его здоровье
    if not check_bot_health():
        logger.warning("Бот нездоров, перезапускаем")
        kill_bot_processes()
        time.sleep(2)  # Даем время на корректное завершение
        start_bot()

def main():
    """Основная функция мониторинга."""
    logger.info("Запуск монитора бота")
    
    # Инициализируем файл здоровья
    update_health_check()
    
    # Проверяем, запущен ли бот, и запускаем, если нет
    if not is_bot_running():
        logger.info("Бот не запущен, запускаем")
        start_bot()
    
    # Основной цикл мониторинга
    try:
        while True:
            check_and_restart_if_needed()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Монитор остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в мониторе: {e}")
        raise

if __name__ == "__main__":
    main()
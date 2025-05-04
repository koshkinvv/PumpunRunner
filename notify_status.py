#!/usr/bin/env python
"""
Скрипт для отправки уведомлений о состоянии бота администратору через Telegram.
Использует тот же токен бота, что и основное приложение.
"""

import os
import sys
import time
import json
import psutil
import logging
import argparse
import datetime
import subprocess
import requests

from telegram import Bot
import asyncio

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('status_notifier')

# Получаем токен из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("Переменная окружения TELEGRAM_TOKEN не установлена!")
    sys.exit(1)

# ID администратора (можно изменить на ваш ID)
ADMIN_ID = None  # Заполнится при первом запуске

# Путь к файлу здоровья бота
HEALTH_FILE = "bot_health.txt"

def get_bot_health():
    """Получает информацию о состоянии здоровья бота."""
    if not os.path.exists(HEALTH_FILE):
        return {
            "status": "unknown",
            "last_update": None,
            "alive": False,
            "message": "Файл состояния не найден"
        }
    
    try:
        with open(HEALTH_FILE, "r") as f:
            last_update = f.read().strip()
        
        last_time = datetime.datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.datetime.now()
        
        time_diff = (current_time - last_time).total_seconds()
        
        if time_diff <= 60:
            status = "healthy"
            message = "Бот работает нормально"
            alive = True
        elif time_diff <= 300:
            status = "warning"
            message = f"Последнее обновление {int(time_diff // 60)} мин назад"
            alive = True
        else:
            status = "critical"
            message = f"Последнее обновление {int(time_diff // 60)} мин назад"
            alive = False
        
        return {
            "status": status,
            "last_update": last_update,
            "alive": alive,
            "message": message,
            "seconds_since_update": int(time_diff)
        }
    except Exception as e:
        logger.error(f"Ошибка при получении состояния бота: {e}")
        return {
            "status": "error",
            "last_update": None,
            "alive": False,
            "message": f"Ошибка: {str(e)}"
        }

def get_system_stats():
    """Получает информацию о состоянии системы."""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": memory.percent,
            "memory_used": memory.used // (1024 * 1024),  # В МБ
            "memory_total": memory.total // (1024 * 1024),  # В МБ
            "disk_percent": disk.percent,
            "disk_used": disk.used // (1024 * 1024 * 1024),  # В ГБ
            "disk_total": disk.total // (1024 * 1024 * 1024),  # В ГБ
            "uptime": int(time.time() - psutil.boot_time()),  # В секундах
        }
    except Exception as e:
        logger.error(f"Ошибка при получении системной статистики: {e}")
        return {
            "error": str(e)
        }

def get_bot_processes():
    """Получает информацию о процессах бота."""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent', 'create_time']):
            try:
                if proc.info['cmdline'] and any(cmd in str(proc.info['cmdline']) for cmd in ['main.py', 'bot_monitor.py', 'run.py']):
                    # Получаем дополнительную информацию
                    proc_info = proc.as_dict(['pid', 'name', 'cpu_percent', 'memory_percent', 'create_time'])
                    proc_info['cmdline'] = ' '.join(proc.info['cmdline'])
                    proc_info['running_time'] = int(time.time() - proc.info['create_time'])
                    processes.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return processes
    except Exception as e:
        logger.error(f"Ошибка при получении информации о процессах: {e}")
        return []

def get_recent_errors(num_lines=20):
    """Получает последние ошибки из лог-файлов."""
    try:
        if not os.path.exists("logs"):
            return {}
            
        errors = {}
        log_files = [f for f in os.listdir("logs") if f.endswith(".log")]
        
        for log_file in log_files[:5]:  # Берем только 5 самых последних файлов
            file_path = os.path.join("logs", log_file)
            try:
                with open(file_path, "r") as f:
                    content = f.readlines()
                
                # Фильтруем только строки с ошибками (содержащие ERROR или Exception)
                error_lines = [line for line in content if 'ERROR' in line or 'Exception' in line or 'error' in line.lower()]
                if error_lines:
                    errors[log_file] = error_lines[-num_lines:] if len(error_lines) > num_lines else error_lines
            except Exception as e:
                errors[log_file] = [f"Ошибка чтения файла: {str(e)}"]
        
        return errors
    except Exception as e:
        logger.error(f"Ошибка при получении логов ошибок: {e}")
        return {"error": str(e)}

async def send_notification(admin_id, message, parse_mode=None):
    """Отправляет уведомление администратору через Telegram."""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(
            chat_id=admin_id,
            text=message,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
        return False

async def send_status_report(admin_id, event_type="regular"):
    """Отправляет отчет о состоянии бота администратору."""
    health = get_bot_health()
    system = get_system_stats()
    processes = get_bot_processes()
    errors = get_recent_errors()
    
    # Формируем сообщение в зависимости от типа события
    if event_type == "startup":
        header = "🚀 *Бот запущен*\n\n"
    elif event_type == "critical":
        header = "🔴 *КРИТИЧЕСКОЕ СОСТОЯНИЕ БОТА*\n\n"
    elif event_type == "warning":
        header = "⚠️ *Предупреждение*\n\n"
    else:
        header = "📊 *Отчет о состоянии бота*\n\n"
    
    # Формируем информацию о здоровье
    health_status = {
        "healthy": "✅ Активен",
        "warning": "⚠️ Требует внимания",
        "critical": "🔴 Критическое состояние",
        "unknown": "❓ Неизвестно",
        "error": "⚠️ Ошибка проверки"
    }.get(health["status"], "❓ Неизвестно")
    
    health_info = f"*Состояние бота:* {health_status}\n"
    health_info += f"*Сообщение:* {health['message']}\n"
    if health["last_update"]:
        health_info += f"*Последнее обновление:* {health['last_update']}\n"
    
    # Информация о системе
    if "error" in system:
        system_info = f"*Ошибка получения системной информации:* {system['error']}\n"
    else:
        system_info = f"*CPU:* {system['cpu_percent']}%\n"
        system_info += f"*Память:* {system['memory_used']} МБ из {system['memory_total']} МБ ({system['memory_percent']}%)\n"
        system_info += f"*Диск:* {system['disk_used']} ГБ из {system['disk_total']} ГБ ({system['disk_percent']}%)\n"
        uptime_hours = system['uptime'] // 3600
        uptime_mins = (system['uptime'] % 3600) // 60
        system_info += f"*Время работы VM:* {uptime_hours} ч. {uptime_mins} мин.\n"
    
    # Информация о процессах
    if processes:
        process_info = "*Активные процессы бота:*\n"
        for proc in processes:
            runtime_hours = proc['running_time'] // 3600
            runtime_mins = (proc['running_time'] % 3600) // 60
            process_info += f"- PID {proc['pid']}: {proc['name']} (CPU: {proc['cpu_percent']:.1f}%, Память: {proc['memory_percent']:.1f}%, Время: {runtime_hours} ч. {runtime_mins} мин.)\n"
    else:
        process_info = "*Процессы бота не обнаружены*\n"
    
    # Информация об ошибках
    if errors and any(errors.values()):
        error_info = "*Последние ошибки:*\n"
        for log_file, error_lines in errors.items():
            if error_lines:
                error_info += f"Из {log_file}:\n"
                for i, line in enumerate(error_lines[-3:]):  # Показываем максимум 3 последние ошибки из каждого файла
                    error_info += f"  {i+1}. `{line.strip()[:100]}...`\n" if len(line.strip()) > 100 else f"  {i+1}. `{line.strip()}`\n"
    else:
        error_info = "*Ошибок не обнаружено*\n"
    
    # Собираем полное сообщение
    message = f"{header}{health_info}\n{system_info}\n{process_info}\n{error_info}"
    
    # Добавляем рекомендации, если есть проблемы
    if health['status'] in ['critical', 'warning'] or not processes:
        message += "\n*Рекомендации:*\n"
        if not processes:
            message += "- Запустите бота командой `python run.py`\n"
        elif health['status'] == 'critical':
            message += "- Проверьте логи на наличие ошибок\n"
            message += "- Перезапустите бота командой `python run.py`\n"
        elif health['status'] == 'warning':
            message += "- Мониторьте состояние бота\n"
    
    # Отправляем сообщение
    sent = await send_notification(admin_id, message, parse_mode="Markdown")
    return sent

async def find_admin():
    """Находит администратора бота (первого пользователя, который написал боту)."""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        updates = await bot.get_updates(limit=100, timeout=10)
        
        if updates:
            # Пытаемся найти первого пользователя, который не является ботом
            for update in updates:
                if update.message and update.message.from_user and not update.message.from_user.is_bot:
                    return update.message.from_user.id
        
        # Если не нашли, возвращаем None
        return None
    except Exception as e:
        logger.error(f"Ошибка при поиске администратора: {e}")
        return None

async def main():
    parser = argparse.ArgumentParser(description='Отправка уведомлений о состоянии бота')
    parser.add_argument('--admin-id', type=int, help='ID администратора в Telegram')
    parser.add_argument('--type', choices=['regular', 'startup', 'critical', 'warning'], 
                        default='regular', help='Тип уведомления')
    parser.add_argument('--check', action='store_true', help='Проверить состояние бота и отправить уведомление при проблемах')
    args = parser.parse_args()
    
    global ADMIN_ID
    ADMIN_ID = args.admin_id
    
    # Если ID администратора не указан, пытаемся найти его
    if not ADMIN_ID:
        ADMIN_ID = await find_admin()
        if not ADMIN_ID:
            logger.error("Не удалось определить ID администратора! Укажите его явно с помощью параметра --admin-id")
            return
    
    logger.info(f"Используем ID администратора: {ADMIN_ID}")
    
    if args.check:
        # Проверяем состояние бота и отправляем уведомление только при проблемах
        health = get_bot_health()
        processes = get_bot_processes()
        
        if health['status'] == 'critical':
            logger.info("Обнаружено критическое состояние бота, отправляем уведомление")
            await send_status_report(ADMIN_ID, event_type="critical")
        elif health['status'] == 'warning':
            logger.info("Обнаружено предупреждение о состоянии бота, отправляем уведомление")
            await send_status_report(ADMIN_ID, event_type="warning")
        elif not processes:
            logger.info("Процессы бота не обнаружены, отправляем критическое уведомление")
            await send_status_report(ADMIN_ID, event_type="critical")
        else:
            logger.info("Состояние бота в норме, уведомление не требуется")
    else:
        # Отправляем полный отчет о состоянии
        await send_status_report(ADMIN_ID, event_type=args.type)

if __name__ == "__main__":
    asyncio.run(main())
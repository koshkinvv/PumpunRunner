#!/usr/bin/env python
"""
Веб-приложение для мониторинга состояния бота и просмотра статистики.
"""

import os
import sys
import json
import time
import logging
import datetime
import psutil
from flask import Flask, render_template, jsonify
from sqlalchemy.orm import DeclarativeBase
from flask_sqlalchemy import SQLAlchemy

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('bot_webapp')

class Base(DeclarativeBase):
    pass

# Создаем приложение Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key")

# Настраиваем базу данных
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Инициализируем базу данных
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Обеспечиваем импорт моделей и создание таблиц
with app.app_context():
    import models  # noqa: F401
    db.create_all()

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

def get_recent_logs(num_lines=100):
    """Получает последние строки из файлов логов."""
    try:
        if not os.path.exists("logs"):
            return {}
            
        logs = {}
        log_files = [f for f in os.listdir("logs") if f.endswith(".log")]
        
        for log_file in log_files[:5]:  # Берем только 5 самых последних файлов
            file_path = os.path.join("logs", log_file)
            try:
                with open(file_path, "r") as f:
                    content = f.readlines()
                logs[log_file] = content[-num_lines:] if len(content) > num_lines else content
            except Exception as e:
                logs[log_file] = [f"Ошибка чтения файла: {str(e)}"]
        
        return logs
    except Exception as e:
        logger.error(f"Ошибка при получении логов: {e}")
        return {"error": str(e)}

@app.route("/")
def index():
    """Главная страница с информацией о состоянии бота."""
    return render_template(
        "index.html",
        health=get_bot_health(),
        system=get_system_stats(),
        processes=get_bot_processes()
    )

@app.route("/status")
def status():
    """API-эндпоинт для получения статуса бота в формате JSON."""
    return jsonify({
        "health": get_bot_health(),
        "system": get_system_stats(),
        "processes": get_bot_processes(),
    })

@app.route("/logs")
def logs():
    """Страница с логами бота."""
    return render_template(
        "logs.html",
        logs=get_recent_logs()
    )

@app.route("/about")
def about():
    """Страница с информацией о боте."""
    return render_template("about.html")

# Интеграция со скриптами бота
@app.route("/update-health", methods=["POST"])
def update_health():
    """Обновляет файл здоровья бота."""
    try:
        with open(HEALTH_FILE, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Запуск приложения
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
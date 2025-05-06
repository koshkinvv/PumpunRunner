"""
Скрипт для запуска веб-приложения и обновленного бота.
"""
import logging
import os
import subprocess
import threading
import time
from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определение базового класса моделей
class Base(DeclarativeBase):
    pass

# Инициализация Flask и SQLAlchemy
db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Настройка БД
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Глобальная переменная для хранения процесса бота
bot_process = None
bot_logs = []

def add_log(message, level="INFO"):
    """Добавляет сообщение в лог бота."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    bot_logs.append(log_entry)
    # Ограничиваем количество логов в памяти
    if len(bot_logs) > 100:
        bot_logs.pop(0)
    print(log_entry)

def start_bot():
    """Запускает процесс бота."""
    global bot_process
    if bot_process and bot_process.poll() is None:
        add_log("Бот уже запущен", "WARNING")
        return False

    try:
        add_log("Запуск бота...")
        bot_process = subprocess.Popen(
            ["python", "run_updated_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        # Запускаем поток для чтения вывода
        thread = threading.Thread(target=read_bot_output, daemon=True)
        thread.start()
        add_log("Бот успешно запущен", "INFO")
        return True
    except Exception as e:
        add_log(f"Ошибка при запуске бота: {e}", "ERROR")
        return False

def read_bot_output():
    """Читает вывод процесса бота и добавляет его в лог."""
    global bot_process
    if bot_process:
        for line in bot_process.stdout:
            add_log(line.strip(), "BOT")

def stop_bot():
    """Останавливает процесс бота."""
    global bot_process
    if bot_process and bot_process.poll() is None:
        try:
            add_log("Остановка бота...")
            bot_process.terminate()
            bot_process.wait(timeout=5)
            add_log("Бот успешно остановлен", "INFO")
            return True
        except subprocess.TimeoutExpired:
            bot_process.kill()
            add_log("Бот принудительно остановлен", "WARNING")
            return True
        except Exception as e:
            add_log(f"Ошибка при остановке бота: {e}", "ERROR")
            return False
    else:
        add_log("Бот не запущен", "WARNING")
        return False

@app.before_request
def initialize_request():
    """Выполняется перед каждым запросом."""
    pass

@app.route('/initialize')
def initialize():
    """Маршрут для инициализации бота."""
    with app.app_context():
        # Импортируем модели и создаем таблицы
        import models
        db.create_all()
        add_log("БД инициализирована", "INFO")
    return jsonify({"status": "success", "message": "БД успешно инициализирована"})

@app.route('/')
def index():
    """Главная страница."""
    # Проверяем, запущен ли бот
    running = bot_process and bot_process.poll() is None
    bot_status = {
        "running": running,
        "last_start": time.strftime("%Y-%m-%d %H:%M:%S") if running else None,
        "last_error": None,
        "log": [{"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), 
                 "level": "INFO" if "INFO" in log else ("WARNING" if "WARNING" in log else "ERROR"), 
                 "message": log} for log in bot_logs]
    }
    
    # Подготовим переменные окружения для отображения (показываем только наличие, не значения)
    env_vars = {
        "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN") is not None,
        "DATABASE_URL": os.environ.get("DATABASE_URL") is not None,
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY") is not None
    }
    
    return render_template('index.html', bot_status=bot_status, env_vars=env_vars)

@app.route('/api/bot/status')
def api_bot_status():
    """API для получения статуса бота."""
    running = bot_process and bot_process.poll() is None
    return jsonify({"running": running})

@app.route('/api/bot/start')
def api_bot_start():
    """API для запуска бота."""
    success = start_bot()
    return jsonify({"success": success})

@app.route('/api/bot/stop')
def api_bot_stop():
    """API для остановки бота."""
    success = stop_bot()
    return jsonify({"success": success})

@app.route('/api/bot/restart')
def api_bot_restart():
    """API для перезапуска бота."""
    stop_bot()
    time.sleep(1)  # Небольшая задержка
    success = start_bot()
    return jsonify({"success": success})

@app.route('/api/bot/logs')
def api_bot_logs():
    """API для получения логов бота."""
    logs = []
    for log in bot_logs:
        logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": "INFO" if "INFO" in log else ("WARNING" if "WARNING" in log else "ERROR"),
            "message": log
        })
    return jsonify({"logs": logs})

@app.route('/status')
def status():
    """API для проверки статуса сервера."""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Инициализируем БД перед запуском
    with app.app_context():
        # Импортируем модели и создаем таблицы
        import models
        db.create_all()
        add_log("БД инициализирована", "INFO")

    # Запускаем бота при старте приложения
    start_bot()

    # Запускаем Flask-приложение
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
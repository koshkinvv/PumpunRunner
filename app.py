"""
Основное веб-приложение Flask для API и управления ботом.
"""
import os
import sys
import logging
import threading
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Инициализация Flask и SQLAlchemy
class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "supersecretkey")

# Конфигурация базы данных
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)


# Глобальная переменная для отслеживания процесса бота
bot_process = None
bot_status = {
    "running": False,
    "last_start": None,
    "last_error": None,
    "log": []
}


def add_log(message, level="INFO"):
    """Добавляет сообщение в лог бота."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"timestamp": timestamp, "level": level, "message": message}
    bot_status["log"].insert(0, entry)
    # Ограничиваем размер лога
    if len(bot_status["log"]) > 100:
        bot_status["log"].pop()
    
    # Также выводим в общий лог
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)


def start_bot():
    """Запускает процесс бота."""
    global bot_process, bot_status
    
    try:
        # Если процесс уже запущен, ничего не делаем
        if bot_process and bot_process.poll() is None:
            add_log("Бот уже запущен", "WARNING")
            return True
        
        # Запускаем процесс бота
        add_log("Запуск бота...")
        
        # Используем deploy_runner.py для запуска бота
        cmd = [sys.executable, "deploy_runner.py"]
        bot_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Обновляем статус
        bot_status["running"] = True
        bot_status["last_start"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_status["last_error"] = None
        
        # Запускаем поток для чтения вывода бота
        threading.Thread(target=read_bot_output, daemon=True).start()
        
        add_log("Бот успешно запущен")
        return True
    
    except Exception as e:
        bot_status["running"] = False
        bot_status["last_error"] = str(e)
        add_log(f"Ошибка при запуске бота: {e}", "ERROR")
        return False


def read_bot_output():
    """Читает вывод процесса бота и добавляет его в лог."""
    global bot_process, bot_status
    
    if not bot_process:
        return
    
    for line in bot_process.stdout:
        line = line.strip()
        if line:
            if "error" in line.lower() or "exception" in line.lower():
                add_log(f"Bot: {line}", "ERROR")
            else:
                add_log(f"Bot: {line}")
    
    # Когда поток завершается, проверяем статус процесса
    return_code = bot_process.poll()
    if return_code is not None:
        add_log(f"Процесс бота завершился с кодом: {return_code}", 
                "ERROR" if return_code != 0 else "INFO")
        bot_status["running"] = False


def stop_bot():
    """Останавливает процесс бота."""
    global bot_process, bot_status
    
    if not bot_process:
        add_log("Процесс бота не запущен", "WARNING")
        return True
    
    try:
        add_log("Остановка бота...")
        
        # Пытаемся корректно завершить процесс
        bot_process.terminate()
        
        # Ждем немного для корректного завершения
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            add_log("Бот не остановился корректно, выполняем принудительное завершение", "WARNING")
            bot_process.kill()
        
        # Обновляем статус
        bot_status["running"] = False
        add_log("Бот успешно остановлен")
        
        return True
    
    except Exception as e:
        add_log(f"Ошибка при остановке бота: {e}", "ERROR")
        return False


# При запуске сервера автоматически запускаем бота
# Инициализация БД при запуске
try:
    with app.app_context():
        import models  # noqa
        db.create_all()
        add_log("База данных инициализирована при запуске")
except Exception as e:
    add_log(f"Ошибка при инициализации БД при запуске: {e}", "ERROR")

# Дополнительная инициализация при запросе
@app.before_request
def initialize_request():
    """Выполняется перед каждым запросом."""
    # Здесь можно добавить логику, которая должна выполняться перед запросами
    pass


@app.route('/init')
def initialize():
    """Маршрут для инициализации бота."""
    try:
        # Запускаем бота
        success = start_bot()
        if success:
            add_log("Веб-приложение успешно инициализировано")
            return jsonify({"status": "ok", "message": "Бот запущен"})
        else:
            return jsonify({"status": "error", "message": "Не удалось запустить бота"}), 500
    
    except Exception as e:
        add_log(f"Ошибка при инициализации: {e}", "ERROR")
        return jsonify({"status": "error", "message": str(e)}), 500


# Маршруты веб-приложения
@app.route('/')
def index():
    """Главная страница."""
    env_vars = {
        "TELEGRAM_TOKEN": bool(os.environ.get("TELEGRAM_TOKEN")),
        "DATABASE_URL": bool(os.environ.get("DATABASE_URL")),
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY"))
    }
    
    return render_template(
        'index.html',
        bot_status=bot_status,
        env_vars=env_vars
    )


@app.route('/api/bot/status')
def api_bot_status():
    """API для получения статуса бота."""
    return jsonify({
        "running": bot_status["running"],
        "last_start": bot_status["last_start"],
        "last_error": bot_status["last_error"],
        "log_count": len(bot_status["log"])
    })


@app.route('/api/bot/start')
def api_bot_start():
    """API для запуска бота."""
    result = start_bot()
    return jsonify({"success": result})


@app.route('/api/bot/stop')
def api_bot_stop():
    """API для остановки бота."""
    result = stop_bot()
    return jsonify({"success": result})


@app.route('/api/bot/restart')
def api_bot_restart():
    """API для перезапуска бота."""
    stop_bot()
    result = start_bot()
    return jsonify({"success": result})


@app.route('/api/bot/logs')
def api_bot_logs():
    """API для получения логов бота."""
    return jsonify({"logs": bot_status["log"]})


@app.route('/api/status')
def status():
    """API для проверки статуса сервера."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "bot_running": bot_status["running"]
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
#!/usr/bin/env python
"""
Webhook-сервер для Telegram-бота с поддержкой healthcheck.
Это гарантирует, что Replit Reserved VM не будет "засыпать".
"""

import os
import json
import logging
import datetime
from flask import Flask, request, jsonify, Blueprint
from telegram import Update
from bot_modified import setup_bot

# Получаем токен Telegram из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Отсутствует переменная окружения TELEGRAM_TOKEN")

# Путь к файлу здоровья бота
HEALTH_FILE = "bot_health.txt"

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("webhook_server")

# Создаем Blueprint для webhook-функциональности
webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
async def webhook():
    """Обрабатывает входящие обновления от Telegram."""
    try:
        # Обновляем файл здоровья
        update_health_check()
        
        # Получаем данные обновления от Telegram
        if request.headers.get("content-type") == "application/json":
            update_data = request.get_json()
            logger.debug(f"Получено обновление: {update_data}")
            
            # Преобразуем JSON в объект Update
            update = Update.de_json(update_data, bot.bot)
            
            # Передаем обновление в диспетчер
            await bot.process_update(update)
            return jsonify({"status": "ok"})
        else:
            logger.warning(f"Получен неподдерживаемый content-type: {request.headers.get('content-type')}")
            return jsonify({"status": "error", "message": "Content-type должен быть application/json"}), 400
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook-обновления: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@webhook_bp.route("/health", methods=["GET"])
def health():
    """Endpoint для проверки работоспособности бота."""
    try:
        # Обновляем файл здоровья при каждом запросе
        update_health_check()
        
        # Получаем время последнего обновления из файла
        health_info = get_bot_health()
        
        # Возвращаем информацию о здоровье бота
        return jsonify(health_info)
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья бота: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        with open(HEALTH_FILE, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла проверки здоровья: {e}")

def register_webhook_routes(app, telegram_bot=None):
    """Регистрирует маршруты webhook в приложении Flask.
    
    Args:
        app: Flask приложение
        telegram_bot: Экземпляр бота Telegram для обработки обновлений (опционально)
    """
    # Если передан экземпляр бота, сохраняем его глобально
    if telegram_bot:
        global bot
        bot = telegram_bot
        
    # Проверяем, зарегистрирован ли уже blueprint
    try:
        app.register_blueprint(webhook_bp, url_prefix="/webhook")
        return True
    except ValueError as e:
        # Blueprint уже зарегистрирован, это нормально
        logger.info(f"Blueprint уже зарегистрирован: {e}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при регистрации blueprint: {e}")
        return False

async def setup_webhook(telegram_bot, webhook_url=None):
    """Настраивает вебхук для Telegram-бота."""
    global bot
    bot = telegram_bot
    
    if not webhook_url:
        # Используем REPLIT_DEV_DOMAIN для правильного домена Replit
        replit_domain = os.environ.get("REPLIT_DEV_DOMAIN")
        if replit_domain:
            # Используем главный домен и порт 5000, который прослушивается основным приложением
            webhook_url = f"https://{replit_domain}/webhook/{TELEGRAM_TOKEN}"
        else:
            logger.warning("Не удалось определить URL вебхука. Установите переменную окружения REPL_SLUG.")
            return False
    
    try:
        # Устанавливаем вебхук
        logger.info(f"Устанавливаем вебхук на URL: {webhook_url}")
        await bot.bot.set_webhook(url=webhook_url)
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке вебхука: {e}")
        return False

# Если файл запущен напрямую, настраиваем вебхук
if __name__ == "__main__":
    # Создаем Flask-приложение
    app = Flask(__name__)
    
    # Регистрируем маршруты webhook
    register_webhook_routes(app)
    
    # Создаем и настраиваем бота
    bot = setup_bot()
    
    # Настраиваем вебхук
    setup_webhook(bot)
    
    # Запускаем Flask-сервер на другом порту, чтобы избежать конфликта
    app.run(host="0.0.0.0", port=8080)
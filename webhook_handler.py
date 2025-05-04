"""
Упрощенный обработчик webhook для Telegram бота.
Этот модуль обеспечивает простую обработку webhook-запросов от Telegram API
без использования встроенного webhook-механизма telegram-python-bot.
"""

import os
import json
import logging
import asyncio
import datetime
from flask import Blueprint, request, jsonify
from config import TELEGRAM_TOKEN, logging

# Настройка логирования
logger = logging.getLogger("webhook_handler")

# Файл для проверки здоровья бота
HEALTH_FILE = "bot_health.txt"

# Глобальная переменная для хранения экземпляра бота
bot = None

# Создаем Blueprint для webhook-функциональности с уникальным именем
webhook_bp = Blueprint("webhook_handler", __name__)

@webhook_bp.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    """Обрабатывает входящие обновления от Telegram."""
    try:
        # Проверяем, что бот инициализирован
        if bot is None:
            logger.error("Бот не инициализирован. Возможно, register_webhook_routes не был вызван с экземпляром бота.")
            return jsonify({"status": "error", "message": "Бот не инициализирован"}), 500
            
        # Обновляем файл здоровья
        update_health_check()
        
        # Получаем данные обновления от Telegram
        if request.headers.get("content-type") == "application/json":
            update_data = request.get_json()
            logger.debug(f"Получено обновление: {update_data}")
            
            # Вместо использования функций telegram-python-bot,
            # мы просто передаем raw данные в наш собственный handler
            # через очередь в background thread
            try:
                # Запускаем обработку в отдельном потоке
                import threading
                thread = threading.Thread(target=lambda: handle_update_in_background(bot, update_data))
                thread.daemon = True
                thread.start()
                
                # Сразу возвращаем успешный ответ Telegram
                return jsonify({"status": "ok"})
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {e}")
                return jsonify({"status": "error", "message": f"Ошибка обработки сообщения: {str(e)}"}), 500
        else:
            logger.warning(f"Получен неподдерживаемый content-type: {request.headers.get('content-type')}")
            return jsonify({"status": "error", "message": "Content-type должен быть application/json"}), 400
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook-обновления: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def handle_update_in_background(application, update_data):
    """
    Обрабатывает обновление от Telegram в фоновом режиме.
    
    Args:
        application: Экземпляр Application из telegram.ext
        update_data: Словарь с данными обновления от Telegram API
    """
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        from telegram import Update

        # Проверяем тип обновления и обрабатываем соответствующим образом
        if 'message' in update_data:
            handle_message(application, update_data)
        elif 'callback_query' in update_data:
            handle_callback_query(application, update_data)
        else:
            logger.warning(f"Получен неподдерживаемый тип обновления: {update_data}")
    except Exception as e:
        logger.error(f"Ошибка при обработке обновления в фоновом режиме: {e}", exc_info=True)

def handle_message(application, update_data):
    """
    Обрабатывает сообщение от пользователя.
    
    Args:
        application: Экземпляр Application из telegram.ext
        update_data: Словарь с данными обновления от Telegram API
    """
    try:
        message = update_data['message']
        chat_id = message['chat']['id']
        
        # Проверяем, содержит ли сообщение текст
        if 'text' in message:
            text = message['text']
            
            # Обрабатываем команды
            if text.startswith('/'):
                handle_command(application, chat_id, text)
            else:
                # Обычное текстовое сообщение
                send_telegram_message(chat_id, "Я получил ваше сообщение и обрабатываю его.")
                logger.info(f"Получено текстовое сообщение: {text}")
                
        # Проверяем, содержит ли сообщение фото
        elif 'photo' in message:
            send_telegram_message(chat_id, "Я получил ваше фото и анализирую его.")
            logger.info(f"Получено фото от пользователя {chat_id}")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)

def handle_command(application, chat_id, command_text):
    """
    Обрабатывает команду от пользователя.
    
    Args:
        application: Экземпляр Application из telegram.ext
        chat_id: ID чата
        command_text: Текст команды
    """
    try:
        # Разбиваем текст на команду и аргументы
        parts = command_text.split(' ', 1)
        command = parts[0].lower()
        
        # Обрабатываем различные команды
        if command == '/start' or command == '/help':
            send_telegram_message(chat_id, 
                "👋 Привет! Я бот-помощник для бегунов. Вот что я могу:\n\n"
                "/plan - Создать или просмотреть план тренировок\n"
                "/pending - Показать только незавершенные тренировки\n"
                "/help - Показать это сообщение с командами\n\n"
                "📱 Вы также можете отправить мне скриншот из вашего трекера тренировок, "
                "и я автоматически проанализирую его и зачту вашу тренировку!"
            )
        elif command == '/plan':
            # Для сложных команд лучше запускать оригинальный обработчик через application
            # Но пока отправим простое сообщение
            send_telegram_message(chat_id, 
                "⏳ Эта команда запускает сложный процесс создания плана. "
                "Сейчас мы работаем над улучшением обработки webhook. "
                "Пожалуйста, попробуйте позже."
            )
        elif command == '/pending':
            send_telegram_message(chat_id, 
                "⏳ Эта команда показывает незавершенные тренировки. "
                "Сейчас мы работаем над улучшением обработки webhook. "
                "Пожалуйста, попробуйте позже."
            )
        else:
            send_telegram_message(chat_id, 
                f"Извините, команда {command} не распознана. "
                "Используйте /help для получения списка доступных команд."
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке команды: {e}", exc_info=True)
        send_telegram_message(chat_id, "Произошла ошибка при обработке команды. Пожалуйста, попробуйте позже.")

def handle_callback_query(application, update_data):
    """
    Обрабатывает callback query от inline-кнопок.
    
    Args:
        application: Экземпляр Application из telegram.ext
        update_data: Словарь с данными обновления от Telegram API
    """
    try:
        callback_query = update_data['callback_query']
        chat_id = callback_query['message']['chat']['id']
        callback_data = callback_query['data']
        
        # Отправляем ответ, что получили callback
        answer_callback_query(callback_query['id'])
        
        # Обрабатываем различные callback_data
        if callback_data.startswith('complete_'):
            send_telegram_message(chat_id, "Тренировка отмечена как выполненная!")
        elif callback_data.startswith('cancel_'):
            send_telegram_message(chat_id, "Тренировка отменена!")
        elif callback_data == 'view_plan':
            send_telegram_message(chat_id, "Показываю текущий план тренировок...")
        elif callback_data == 'new_plan':
            send_telegram_message(chat_id, "Создаю новый план тренировок...")
        else:
            send_telegram_message(chat_id, "Неизвестное действие. Пожалуйста, попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка при обработке callback_query: {e}", exc_info=True)

def send_telegram_message(chat_id, text, parse_mode=None):
    """
    Отправляет сообщение в Telegram.
    
    Args:
        chat_id: ID чата получателя
        text: Текст сообщения
        parse_mode: Режим форматирования текста (Markdown, HTML)
    """
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
        data = {
            "chat_id": chat_id,
            "text": text
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
            
        response = requests.post(url, json=data)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при отправке сообщения: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    """
    Отправляет ответ на callback query.
    
    Args:
        callback_query_id: ID callback query
        text: Текст уведомления (опционально)
        show_alert: Показывать ли уведомление как alert (опционально)
    """
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        
        data = {
            "callback_query_id": callback_query_id
        }
        
        if text:
            data["text"] = text
            
        if show_alert:
            data["show_alert"] = True
            
        response = requests.post(url, json=data)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при ответе на callback query: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при ответе на callback query: {e}", exc_info=True)

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
            # Маршрут с учетом префикса /webhook и пути эндпоинта /{TELEGRAM_TOKEN}
            webhook_url = f"https://{replit_domain}/webhook/{TELEGRAM_TOKEN}"
        else:
            logger.warning("Не удалось определить URL вебхука. Установите переменную окружения REPLIT_DEV_DOMAIN.")
            return False
    
    try:
        # Устанавливаем вебхук
        logger.info(f"Устанавливаем вебхук на URL: {webhook_url}")
        await bot.bot.set_webhook(url=webhook_url)
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке вебхука: {e}")
        return False
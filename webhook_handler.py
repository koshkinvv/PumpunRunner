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
import threading
import requests
import uuid
from flask import Blueprint, request, jsonify
from config import TELEGRAM_TOKEN, logging

# Импортируем необходимые модули для управления БД и планами тренировок
try:
    from db_manager import DBManager
    from training_plan_manager import TrainingPlanManager
except ImportError:
    logger = logging.getLogger("webhook_handler")
    logger.error("Не удалось импортировать DBManager или TrainingPlanManager. Некоторая функциональность может быть недоступна.")

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
        # Обновляем файл здоровья в любом случае
        update_health_check()
        
        # Получаем данные обновления от Telegram
        if request.headers.get("content-type") == "application/json":
            update_data = request.get_json()
            update_id = update_data.get("update_id", "unknown")
            logger.info(f"Получено обновление {update_id}")
            
            # Даже если бот не инициализирован, мы можем попытаться обработать простые сообщения
            try:
                # Проверяем, что бот инициализирован
                if bot is None:
                    logger.warning("Бот не инициализирован, используем резервную обработку.")
                    
                    # Обработка сообщений без бота (резервный вариант)
                    if 'message' in update_data and 'chat' in update_data['message']:
                        chat_id = update_data['message']['chat']['id']
                        if 'text' in update_data['message']:
                            text = update_data['message']['text']
                            if text.startswith('/'):
                                # Обработка команд
                                if text == '/start' or text == '/help':
                                    send_telegram_message(chat_id, 
                                        "👋 Привет! Бот сейчас перезагружается. "
                                        "Пожалуйста, попробуйте через несколько минут."
                                    )
                                else:
                                    send_telegram_message(chat_id, 
                                        "⏳ Бот временно недоступен из-за технических работ. "
                                        "Попробуйте позже."
                                    )
                            else:
                                send_telegram_message(chat_id, 
                                    "⏳ Бот временно недоступен из-за технических работ. "
                                    "Попробуйте позже."
                                )
                else:
                    # Используем экземпляр бота для обработки обновления
                    import threading
                    thread = threading.Thread(target=lambda: handle_update_in_background(bot, update_data))
                    thread.daemon = True
                    thread.start()
                    logger.info(f"Обновление {update_id} отправлено на обработку в фоновом режиме")
                
                # Всегда возвращаем 200, чтобы Telegram не отправлял повторно
                return jsonify({"status": "ok"})
            except Exception as e:
                logger.error(f"Ошибка при обработке обновления: {e}", exc_info=True)
                # Возвращаем 200 OK, чтобы Telegram не пытался повторить доставку
                return jsonify({"status": "ok", "message": f"Ошибка: {str(e)}"}), 200
        else:
            logger.warning(f"Получен неподдерживаемый content-type: {request.headers.get('content-type')}")
            return jsonify({"status": "ok", "message": "Неверный формат данных"}), 200
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке webhook: {e}", exc_info=True)
        # Всегда возвращаем 200 OK для Telegram, чтобы избежать повторных отправок
        return jsonify({"status": "ok", "message": f"Критическая ошибка: {str(e)}"}), 200

def handle_update_in_background(application, update_data):
    """
    Обрабатывает обновление от Telegram в фоновом режиме.
    
    Args:
        application: Экземпляр Application из telegram.ext
        update_data: Словарь с данными обновления от Telegram API
    """
    try:
        logger.info(f"Получено обновление: {json.dumps(update_data, ensure_ascii=False)[:200]}...")
        
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
                # Обработка специальных текстовых сообщений
                if text == "👁️ Посмотреть текущий план":
                    # Эмулируем callback query для просмотра плана
                    fake_callback_query = {
                        'id': f"fake_{uuid.uuid4()}",
                        'message': {'chat': {'id': chat_id}, 'message_id': 0},
                        'data': 'view_plan'
                    }
                    handle_callback_query(application, {'callback_query': fake_callback_query})
                    logger.info(f"Обработано сообщение 'Посмотреть текущий план' от пользователя {chat_id}")
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
            # Получаем telegram_id из chat_id
            telegram_id = chat_id
            
            # Импортируем необходимые модули
            from db_manager import DBManager
            from training_plan_manager import TrainingPlanManager
            
            # Создаем класс для кнопки
            class InlineKeyboardButton:
                def __init__(self, text, callback_data):
                    self.text = text
                    self.callback_data = callback_data
                
                def to_dict(self):
                    return {
                        "text": self.text,
                        "callback_data": self.callback_data
                    }
            
            try:
                # Получаем user_id из telegram_id
                db_user_id = DBManager.get_user_id(telegram_id)
                
                if not db_user_id:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш профиль. Пожалуйста, начните заново с команды /start.")
                    return
                
                # Получаем последний план пользователя
                plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                
                if not plan:
                    send_telegram_message(chat_id, "❌ У вас нет активного плана тренировок.")
                    return
                
                # Проверяем структуру плана
                if 'id' not in plan:
                    send_telegram_message(chat_id, "❌ Ошибка структуры плана тренировок: отсутствует ID плана.")
                    logger.error(f"Ошибка структуры плана: отсутствует ID. План: {plan}")
                    return
                
                # Получаем полные данные плана из plan_data
                if 'plan_data' not in plan or not plan['plan_data']:
                    send_telegram_message(chat_id, "❌ Ошибка структуры плана тренировок: отсутствуют данные плана.")
                    logger.error(f"Ошибка структуры плана: отсутствуют данные. План: {plan}")
                    return
                
                # Извлекаем тренировочные дни из данных плана
                plan_data = plan['plan_data']
                if not isinstance(plan_data, dict):
                    send_telegram_message(chat_id, "❌ Ошибка структуры плана тренировок: некорректный формат данных.")
                    logger.error(f"Ошибка структуры плана: неверный формат. План: {plan_data}")
                    return
                
                # Проверяем наличие дней тренировок в плане
                if 'training_days' not in plan_data or not plan_data['training_days']:
                    send_telegram_message(chat_id, "❌ Ваш план тренировок пуст или имеет неверную структуру.")
                    logger.error(f"Ошибка структуры плана: отсутствуют дни тренировок. План: {plan_data}")
                    return
                
                # Получаем выполненные и отмененные тренировки
                plan_id = plan['id']
                completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
                
                # Массив дней тренировок
                training_days = plan_data['training_days']
                
                # Отправляем заголовок плана тренировок
                send_telegram_message(chat_id, f"📅 *Ваш план тренировок:*", parse_mode="Markdown")
                
                # Флаг для разделения предстоящих и прошедших тренировок
                has_upcoming = False
                has_completed = False
                
                # Если есть выполненные или отмененные тренировки, отправляем заголовок
                if any(day_num in completed_days or day_num in canceled_days for day_num in range(1, len(training_days) + 1)):
                    send_telegram_message(chat_id, "*Выполненные и отмененные тренировки:*", parse_mode="Markdown")
                
                # Обрабатываем каждый день тренировки
                for i, day in enumerate(training_days):
                    day_num = i + 1
                    day_info = f"День {day_num}: {day['day']} ({day['date']})\n"
                    day_info += f"Тип: {day['training_type']}\n"
                    day_info += f"Дистанция: {day['distance']}\n"
                    day_info += f"Темп: {day['pace']}\n"
                    day_info += f"Описание: {day['description']}"
                    
                    # Проверяем, выполнена или отменена ли тренировка
                    if day_num in completed_days:
                        send_telegram_message(chat_id, f"✅ {day_info}", parse_mode="Markdown")
                        has_completed = True
                    elif day_num in canceled_days:
                        send_telegram_message(chat_id, f"❌ {day_info}", parse_mode="Markdown")
                        has_completed = True
                    else:
                        has_upcoming = True
                
                # Если есть предстоящие тренировки, отправляем заголовок и сами тренировки
                if has_upcoming:
                    send_telegram_message(chat_id, "*Предстоящие тренировки:*", parse_mode="Markdown")
                    
                    for i, day in enumerate(training_days):
                        day_num = i + 1
                        if day_num not in completed_days and day_num not in canceled_days:
                            day_info = f"День {day_num}: {day['day']} ({day['date']})\n"
                            day_info += f"Тип: {day['training_type']}\n"
                            day_info += f"Дистанция: {day['distance']}\n"
                            day_info += f"Темп: {day['pace']}\n"
                            day_info += f"Описание: {day['description']}"
                            
                            # Создаем кнопки действий для этой тренировки
                            # Создаем словари для кнопок
                            complete_button = {
                                "text": "✅ Выполнено",
                                "callback_data": f"complete_training_{plan_id}_{day_num}"
                            }
                            cancel_button = {
                                "text": "❌ Отменить",
                                "callback_data": f"cancel_training_{plan_id}_{day_num}"
                            }
                            
                            # Создаем клавиатуру в формате Telegram API
                            training_keyboard = [[complete_button, cancel_button]]
                            
                            # Отправляем сообщение с тренировкой и кнопками
                            send_message_with_keyboard(chat_id, f"⏳ {day_info}", training_keyboard, parse_mode="Markdown")
                
                # Если нет ни выполненных, ни предстоящих тренировок
                if not has_completed and not has_upcoming:
                    send_telegram_message(chat_id, "План тренировок пуст.", parse_mode="Markdown")
                
                # Создаём инлайн клавиатуру с кнопками действий для последнего сообщения
                keyboard = []
                
                # Кнопка для нового плана
                new_plan_button = {
                    "text": "🔄 Создать новый план",
                    "callback_data": "new_plan"
                }
                keyboard.append([new_plan_button])
                
                # Отправляем последнее сообщение с клавиатурой
                send_message_with_keyboard(chat_id, "Выберите действие:", keyboard)
            except Exception as e:
                logger.error(f"Ошибка при отображении плана тренировок: {e}", exc_info=True)
                send_telegram_message(chat_id, "❌ Произошла ошибка при получении плана тренировок. Пожалуйста, попробуйте позже.")
        elif callback_data == 'new_plan':
            send_telegram_message(chat_id, "Создаю новый план тренировок...")
        elif callback_data.startswith('complete_training_') or callback_data.startswith('cancel_training_'):
            # Обработка действий с тренировками
            try:
                parts = callback_data.split('_')
                action = parts[0]  # complete или cancel
                plan_id = int(parts[2])
                day_num = int(parts[3])
                
                # Получаем ID пользователя из базы данных
                db_user_id = DBManager.get_user_id(user_id)
                
                if not db_user_id:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш профиль. Пожалуйста, начните заново с команды /start.")
                    return
                
                # Выполняем действие с тренировкой
                if action == 'complete':
                    # Отмечаем тренировку как выполненную
                    success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, day_num)
                    
                    if success:
                        # Получаем данные тренировки
                        plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)
                        
                        if plan and 'plan_data' in plan and plan['plan_data']:
                            plan_data = plan['plan_data']
                            if 'training_days' in plan_data:
                                training_days = plan_data['training_days']
                                
                                if day_num <= len(training_days):
                                    training = training_days[day_num - 1]
                                    distance = training.get('distance', '0 км')
                                    
                                    # Пытаемся извлечь числовое значение из строки дистанции
                                    try:
                                        # Убираем ' км' и пробелы, затем преобразуем в число
                                        distance_value = float(distance.replace('км', '').strip())
                                        
                                        # Обновляем недельный объем бега
                                        DBManager.update_weekly_volume(db_user_id, distance_value)
                                    except:
                                        logger.error(f"Не удалось преобразовать дистанцию '{distance}' в число")
                        
                        answer_callback_query(callback_query_id, "✅ Тренировка отмечена как выполненная!")
                        
                        # Обновляем сообщение, заменяя кнопки на отметку о выполнении
                        message_id = callback_query['message']['message_id']
                        message_text = callback_query['message']['text']
                        
                        # Убираем символ '⏳' и добавляем '✅', добавляем слово "ВЫПОЛНЕНО"
                        if message_text.startswith('⏳'):
                            training_title_end = message_text.find('\n')
                            if training_title_end > 0:
                                # Добавляем " - ВЫПОЛНЕНО" в конец заголовка
                                title = message_text[1:training_title_end]
                                if " - ВЫПОЛНЕНО" not in title:
                                    title += " - ВЫПОЛНЕНО"
                                new_text = '✅' + title + message_text[training_title_end:]
                                message_text = new_text
                            else:
                                message_text = '✅' + message_text[1:]
                        
                        # Редактируем существующее сообщение вместо отправки нового
                        try:
                            # Редактируем сообщение напрямую через API
                            import requests
                            
                            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
                            
                            data = {
                                "chat_id": chat_id,
                                "message_id": message_id,
                                "text": message_text,
                                "parse_mode": "Markdown"
                            }
                                
                            response = requests.post(url, json=data)
                            
                            if response.status_code != 200:
                                logger.error(f"Ошибка при редактировании сообщения: {response.text}")
                                # Как запасной вариант отправляем новое сообщение
                                send_telegram_message(chat_id, message_text, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Ошибка при редактировании сообщения: {e}")
                            # Как запасной вариант отправляем новое сообщение
                            send_telegram_message(chat_id, message_text, parse_mode="Markdown")
                    else:
                        answer_callback_query(callback_query_id, "❌ Не удалось отметить тренировку как выполненную.", show_alert=True)
                        
                elif action == 'cancel':
                    # Отмечаем тренировку как отмененную
                    success = TrainingPlanManager.mark_training_canceled(db_user_id, plan_id, day_num)
                    
                    if success:
                        answer_callback_query(callback_query_id, "❌ Тренировка отменена.")
                        
                        # Обновляем сообщение, заменяя кнопки на отметку об отмене
                        message_id = callback_query['message']['message_id']
                        message_text = callback_query['message']['text']
                        
                        # Убираем символ '⏳' и добавляем '❌', добавляем слово "ОТМЕНЕНО"
                        if message_text.startswith('⏳'):
                            training_title_end = message_text.find('\n')
                            if training_title_end > 0:
                                # Добавляем " - ОТМЕНЕНО" в конец заголовка
                                title = message_text[1:training_title_end]
                                if " - ОТМЕНЕНО" not in title:
                                    title += " - ОТМЕНЕНО"
                                new_text = '❌' + title + message_text[training_title_end:]
                                message_text = new_text
                            else:
                                message_text = '❌' + message_text[1:]
                        
                        # Редактируем существующее сообщение вместо отправки нового
                        try:
                            # Редактируем сообщение напрямую через API
                            import requests
                            
                            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
                            
                            data = {
                                "chat_id": chat_id,
                                "message_id": message_id,
                                "text": message_text,
                                "parse_mode": "Markdown"
                            }
                                
                            response = requests.post(url, json=data)
                            
                            if response.status_code != 200:
                                logger.error(f"Ошибка при редактировании сообщения: {response.text}")
                                # Как запасной вариант отправляем новое сообщение
                                send_telegram_message(chat_id, message_text, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Ошибка при редактировании сообщения: {e}")
                            # Как запасной вариант отправляем новое сообщение
                            send_telegram_message(chat_id, message_text, parse_mode="Markdown")
                        
                        # Предлагаем пользователю скорректировать оставшийся план
                        adjust_button = {
                            "text": "✅ Да, скорректировать",
                            "callback_data": f"adjust_plan_{plan_id}_{day_num}"
                        }
                        no_adjust_button = {
                            "text": "❌ Нет, оставить как есть",
                            "callback_data": "no_adjust"
                        }
                        keyboard = [[adjust_button], [no_adjust_button]]
                        
                        send_message_with_keyboard(
                            chat_id, 
                            "Хотите скорректировать оставшиеся тренировки с учетом пропущенной?", 
                            keyboard
                        )
                    else:
                        answer_callback_query(callback_query_id, "❌ Не удалось отменить тренировку.", show_alert=True)
            except Exception as e:
                logger.error(f"Ошибка при обработке действия с тренировкой: {e}", exc_info=True)
                answer_callback_query(callback_query_id, "❌ Произошла ошибка при обработке действия.", show_alert=True)
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

def send_message_with_keyboard(chat_id, text, keyboard, parse_mode=None):
    """
    Отправляет сообщение в Telegram с инлайн-клавиатурой.
    
    Args:
        chat_id: ID чата получателя
        text: Текст сообщения
        keyboard: Массив кнопок для инлайн-клавиатуры
        parse_mode: Режим форматирования текста (Markdown, HTML)
    """
    try:
        import requests
        import json
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
        # Кнопки уже в формате Telegram API, просто создаем reply_markup
        reply_markup = {
            "inline_keyboard": keyboard
        }
        
        data = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps(reply_markup)
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
            
        response = requests.post(url, json=data)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при отправке сообщения с клавиатурой: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения с клавиатурой: {e}", exc_info=True)

def edit_message_with_keyboard(chat_id, message_id, text, keyboard, parse_mode=None):
    """
    Редактирует сообщение в Telegram, добавляя инлайн-клавиатуру.
    
    Args:
        chat_id: ID чата получателя
        message_id: ID сообщения для редактирования
        text: Новый текст сообщения
        keyboard: Массив кнопок для инлайн-клавиатуры
        parse_mode: Режим форматирования текста (Markdown, HTML)
    """
    try:
        import requests
        import json
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
        
        # Кнопки уже в формате Telegram API, просто создаем reply_markup
        reply_markup = {
            "inline_keyboard": keyboard
        }
        
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": json.dumps(reply_markup)
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
            
        response = requests.post(url, json=data)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при редактировании сообщения с клавиатурой: {response.text}")
            # Если не удалось отредактировать сообщение, отправляем новое
            send_message_with_keyboard(chat_id, text, keyboard, parse_mode)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения с клавиатурой: {e}", exc_info=True)
        # В случае ошибки отправляем новое сообщение
        send_message_with_keyboard(chat_id, text, keyboard, parse_mode)

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
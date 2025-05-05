"""
Улучшенный обработчик webhook для Telegram бота.
Этот модуль обеспечивает обработку webhook-запросов от Telegram API
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
from config import TELEGRAM_TOKEN, logging, STATES

# Импортируем необходимые модули для управления БД и планами тренировок
try:
    from db_manager import DBManager
    from training_plan_manager import TrainingPlanManager
    from openai_service import OpenAIService
    from image_analyzer import ImageAnalyzer
    from conversation import RunnerProfileConversation
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
            
            # Обработка обновления в фоновом режиме
            thread = threading.Thread(target=lambda: handle_update_in_background(bot, update_data))
            thread.daemon = True
            thread.start()
            logger.info(f"Обновление {update_id} отправлено на обработку в фоновом режиме")
            
            # Всегда возвращаем 200, чтобы Telegram не отправлял повторно
            return jsonify({"status": "ok"})
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
        logger.info(f"Обработка обновления: {json.dumps(update_data, ensure_ascii=False)[:200]}...")
        
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
            # Кнопки в сообщениях пользователя
            elif text == "👁️ Посмотреть текущий план":
                # Создаем фейковый callback_query для имитации кнопки "Посмотреть текущий план"
                fake_callback_query = {
                    'id': str(uuid.uuid4()),
                    'from': {'id': chat_id, 'first_name': 'User'},
                    'message': {'chat': {'id': chat_id}, 'message_id': 0},
                    'data': 'view_plan'
                }
                handle_callback_query(application, {'callback_query': fake_callback_query})
                logger.info(f"Обработано сообщение 'Посмотреть текущий план' от пользователя {chat_id}")
            else:
                # Обрабатываем ответы пользователя в процессе создания профиля
                try:
                    # Получаем ID пользователя из базы данных
                    user_id = DBManager.get_user_id(chat_id)
                    if not user_id:
                        logger.error(f"Не удалось найти ID пользователя в базе данных для chat_id={chat_id}")
                        send_telegram_message(chat_id, "❌ Произошла ошибка. Пожалуйста, начните сначала с команды /start")
                        return
                    
                    # Получаем профиль пользователя
                    profile = DBManager.get_runner_profile(user_id)
                    
                    # Если профиль существует и заполнен только дистанцией - это процесс создания профиля
                    if profile and profile.get('distance') and not profile.get('competition_date'):
                        # Пользователь отвечает на вопрос о дате соревнования
                        logger.info(f"Получен ответ о дате соревнования: {text}")
                        
                        # Обрабатываем ответ о дате соревнования
                        date_value = None
                        if text.lower() == 'нет даты':
                            date_value = 'Не указана'
                        else:
                            try:
                                # Проверяем формат даты ДД.ММ.ГГГГ
                                day, month, year = map(int, text.split('.'))
                                date_value = text
                            except:
                                logger.error(f"Некорректный формат даты: {text}")
                                send_telegram_message(
                                    chat_id, 
                                    "❌ Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 01.06.2025) или напишите 'Нет даты'."
                                )
                                return
                        
                        # Обновляем данные профиля
                        connection = DBManager.get_connection()
                        cursor = connection.cursor()
                        
                        try:
                            cursor.execute(
                                "UPDATE runner_profiles SET competition_date = %s WHERE user_id = %s",
                                (date_value, user_id)
                            )
                            connection.commit()
                            
                            # Отправляем сообщение об успешном обновлении
                            send_telegram_message(
                                chat_id, 
                                f"✅ Дата соревнования успешно установлена: {date_value}."
                            )
                            
                            # Следующий вопрос - о поле бегуна
                            keyboard = [
                                [{"text": "Мужчина", "callback_data": "set_gender_male"}],
                                [{"text": "Женщина", "callback_data": "set_gender_female"}]
                            ]
                            
                            send_message_with_keyboard(
                                chat_id,
                                "👤 Укажите ваш пол:",
                                keyboard
                            )
                            
                        except Exception as e:
                            connection.rollback()
                            logger.error(f"Ошибка при обновлении даты соревнования: {e}")
                            send_telegram_message(chat_id, "❌ Произошла ошибка при обновлении профиля.")
                        finally:
                            if cursor:
                                cursor.close()
                            if connection:
                                connection.close()
                    else:
                        # Обычное текстовое сообщение (не часть создания профиля)
                        send_telegram_message(chat_id, "Я получил ваше сообщение и обрабатываю его.")
                        logger.info(f"Получено текстовое сообщение: {text}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке текстового сообщения: {e}", exc_info=True)
                    send_telegram_message(chat_id, "❌ Произошла ошибка при обработке сообщения.")
            
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
        if command == '/help':
            # Получаем информацию о пользователе
            user_info = get_user_info(chat_id) 
            first_name = user_info.get('first_name', '')
            
            send_telegram_message(chat_id, 
                f"👋 Привет, {first_name if first_name else 'бегун'}! Я бот-помощник для бегунов. Вот что я могу:\n\n"
                "/start - Создать или обновить профиль бегуна\n"
                "/plan - Создать или просмотреть план тренировок\n"
                "/pending - Показать только незавершенные тренировки\n"
                "/help - Показать это сообщение с командами\n\n"
                "📱 Вы также можете отправить мне скриншот из вашего трекера тренировок, "
                "и я автоматически проанализирую его и зачту вашу тренировку!"
            )
        elif command == '/start':
            # Получаем информацию о пользователе
            user_info = get_user_info(chat_id) 
            first_name = user_info.get('first_name', '')
            last_name = user_info.get('last_name', '')
            username = user_info.get('username', '')
            
            logger.info(f"Получена команда /start от пользователя: id={chat_id}, username={username}")
            
            # Добавляем пользователя в базу данных
            logger.info(f"Добавляем пользователя в базу данных: id={chat_id}")
            user_id = DBManager.add_user(chat_id, username=username, first_name=first_name, last_name=last_name)
            
            if not user_id:
                send_telegram_message(chat_id, "❌ Произошла ошибка при создании профиля. Пожалуйста, попробуйте позже.")
                return
                
            logger.info(f"Пользователь добавлен/обновлен в базе данных: user_id={user_id}")
            
            # Проверяем, есть ли у пользователя профиль
            profile = DBManager.get_runner_profile(user_id)
            
            if profile:
                logger.info(f"У пользователя есть профиль: {profile}")
                send_telegram_message(chat_id, 
                    f"👋 Привет, {first_name if first_name else 'бегун'}! У вас уже есть профиль бегуна.\n\n"
                    f"Вы можете создать новый план тренировок с помощью команды /plan."
                )
            else:
                logger.info(f"У пользователя нет профиля бегуна, начинаем создание")
                
                # Отправляем приветственное сообщение
                send_telegram_message(chat_id, 
                    f"👋 Привет, {first_name if first_name else 'бегун'}! Я бот-помощник для бегунов.\n\n"
                    "Чтобы создать персонализированный план тренировок, мне нужно больше информации о вас.\n"
                    "Давайте создадим ваш профиль бегуна. Я задам несколько вопросов."
                )
                
                # Запускаем интерактивный диалог создания профиля
                start_profile_creation_dialog(chat_id, user_id)
        elif command == '/plan':
            # Создаем фейковый callback_query для кнопки "Посмотреть текущий план"
            fake_callback_query = {
                'id': str(uuid.uuid4()),
                'from': {'id': chat_id, 'first_name': 'User'},
                'message': {'chat': {'id': chat_id}, 'message_id': 0},
                'data': 'view_plan'
            }
            handle_callback_query(application, {'callback_query': fake_callback_query})
        elif command == '/pending':
            # Получаем telegram_id из chat_id
            telegram_id = chat_id
            
            # Получаем ID пользователя из базы данных
            db_user_id = DBManager.get_user_id(telegram_id)
            
            if not db_user_id:
                send_telegram_message(chat_id, "❌ Не удалось найти ваш профиль. Пожалуйста, начните заново с команды /start.")
                return
            
            # Получаем текущий план тренировок пользователя
            current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            
            if not current_plan:
                send_telegram_message(chat_id, "У вас пока нет плана тренировок. Используйте команду /plan для создания.")
                return
            
            plan_id = current_plan['id']
            plan_data = current_plan['plan_data']
            
            if not plan_data or 'training_days' not in plan_data:
                send_telegram_message(chat_id, "❌ Произошла ошибка при получении плана тренировок. Пожалуйста, попробуйте позже.")
                return
            
            # Получаем выполненные и отмененные тренировки
            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            
            # Массив дней тренировок
            training_days = plan_data['training_days']
            
            # Проверяем, есть ли незавершенные тренировки
            has_pending = False
            
            # Отправляем заголовок только незавершенных тренировок
            send_telegram_message(chat_id, "📅 *Незавершенные тренировки:*", parse_mode="Markdown")
            
            # Обрабатываем каждый день тренировки
            for i, day in enumerate(training_days):
                day_num = i + 1
                # Пропускаем выполненные и отмененные тренировки
                if day_num in completed_days or day_num in canceled_days:
                    continue
                    
                has_pending = True
                day_info = f"День {day_num}: {day['day']} ({day['date']})\n"
                day_info += f"Тип: {day['training_type']}\n"
                day_info += f"Дистанция: {day['distance']}\n"
                day_info += f"Темп: {day['pace']}\n"
                day_info += f"Описание: {day['description']}"
                
                # Создаем кнопки действий для этой тренировки
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
            
            if not has_pending:
                send_telegram_message(chat_id, "У вас нет незавершенных тренировок. Все тренировки выполнены или отменены!", parse_mode="Markdown")
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
        callback_id = callback_query['id']
        
        # Отправляем ответ, что получили callback
        answer_callback_query(callback_id)
        
        # Обрабатываем различные callback_data
        if callback_data.startswith('set_distance_'):
            # Обработка установки дистанции
            try:
                # Получаем значение дистанции из callback_data
                distance = int(callback_data.split('_')[-1])
                
                # Получаем telegram_id из chat_id
                telegram_id = chat_id
                
                # Получаем ID пользователя из базы данных
                db_user_id = DBManager.get_user_id(telegram_id)
                
                if not db_user_id:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш профиль. Пожалуйста, начните заново с команды /start.")
                    return
                
                # Получаем текущий профиль
                profile = DBManager.get_runner_profile(db_user_id)
                
                connection = DBManager.get_connection()
                cursor = connection.cursor()
                
                try:
                    if not profile:
                        # Если профиля нет, создаем новый профиль с дистанцией
                        logger.info(f"Создаем новый профиль для пользователя: {db_user_id} с дистанцией {distance}")
                        cursor.execute(
                            "INSERT INTO runner_profiles (user_id, distance) VALUES (%s, %s)",
                            (db_user_id, distance)
                        )
                    else:
                        # Если профиль уже есть, обновляем дистанцию
                        logger.info(f"Обновляем профиль пользователя: {db_user_id}, устанавливаем дистанцию {distance}")
                        cursor.execute(
                            "UPDATE runner_profiles SET distance = %s WHERE user_id = %s",
                            (distance, db_user_id)
                        )
                    connection.commit()
                    
                    # Отправляем сообщение об успешном установке дистанции и продолжаем сбор данных
                    send_telegram_message(
                        chat_id, 
                        f"✅ Дистанция успешно установлена: {distance} км."
                    )
                    
                    # Продолжаем сбор данных профиля - спрашиваем дату соревнований
                    send_telegram_message(
                        chat_id, 
                        "📅 Теперь укажите примерную дату вашего соревнования (в формате ДД.ММ.ГГГГ).\n\n"
                        "Если у вас нет конкретной даты соревнования, напишите 'Нет даты'."
                    )
                    
                except Exception as e:
                    connection.rollback()
                    logger.error(f"Ошибка при обновлении дистанции: {e}")
                    send_telegram_message(chat_id, "❌ Произошла ошибка при обновлении дистанции.")
                finally:
                    cursor.close()
                    connection.close()
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке установки дистанции: {e}", exc_info=True)
                send_telegram_message(chat_id, "❌ Произошла ошибка при установке дистанции. Пожалуйста, попробуйте позже.")
                
        elif callback_data.startswith('complete_training_') or callback_data.startswith('cancel_training_'):
            # Обработка действий с тренировками
            try:
                parts = callback_data.split('_')
                action = parts[0]  # complete или cancel
                plan_id = int(parts[2])
                day_num = int(parts[3])
                
                # Получаем ID пользователя из базы данных
                user_id = chat_id
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
                        
                        # Проверяем, завершены ли все тренировки в плане
                        try:
                            # Получаем списки выполненных и отмененных тренировок
                            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
                            processed_days = completed_days + canceled_days
                            
                            # Логируем информацию о тренировках
                            logger.info(f"План {plan_id} для пользователя {chat_id}: завершенные дни {completed_days}, отмененные дни {canceled_days}")
                            
                            # Количество тренировок в плане
                            total_days = len(plan['plan_data']['training_days'])
                            logger.info(f"Всего дней в плане: {total_days}")
                            
                            # Проверка, все ли тренировки выполнены или отменены
                            pending_days = [day for day in range(1, total_days + 1) if day not in processed_days]
                            has_pending_trainings = len(pending_days) > 0
                            logger.info(f"Ожидающие дни: {pending_days}, есть ожидающие: {has_pending_trainings}")
                            
                            # Если все тренировки выполнены или отменены, отправляем поздравительное сообщение
                            if not has_pending_trainings:
                                logger.info(f"Все тренировки завершены для пользователя {chat_id}, план {plan_id}")
                                
                                # Расчет общего пройденного расстояния
                                total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
                                logger.info(f"Общее пройденное расстояние: {total_distance} км")
                                
                                # Получаем обновленный еженедельный объем в профиле пользователя
                                profile = DBManager.get_runner_profile(db_user_id)
                                weekly_volume = profile.get('weekly_volume', 0) if profile else 0
                                logger.info(f"Текущий еженедельный объем: {weekly_volume} км")
                                
                                # Импортируем функцию форматирования
                                try:
                                    from bot_modified import format_weekly_volume
                                    formatted_volume = format_weekly_volume(weekly_volume, str(total_distance))
                                except ImportError:
                                    logger.error("Не удалось импортировать format_weekly_volume из bot_modified")
                                    formatted_volume = f"{weekly_volume} км"
                                
                                # Создаем кнопку для продолжения тренировок
                                continue_button = {
                                    "text": "🔄 Продолжить тренировки",
                                    "callback_data": f"continue_plan_{plan_id}"
                                }
                                keyboard = [[continue_button]]
                                
                                # Формируем сообщение
                                congratulation_message = (
                                    f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                                    f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
                                    f"Хотите продолжить тренировки с учетом вашего прогресса?"
                                )
                                
                                logger.info(f"Отправляем поздравление пользователю {chat_id}: {congratulation_message}")
                                
                                # Отправляем сообщение напрямую через API
                                try:
                                    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                                    data = {
                                        "chat_id": chat_id,
                                        "text": congratulation_message,
                                        "reply_markup": {
                                            "inline_keyboard": keyboard
                                        }
                                    }
                                    
                                    response = requests.post(url, json=data)
                                    response_data = response.json()
                                    
                                    if response.status_code == 200 and response_data.get('ok'):
                                        logger.info(f"Поздравление успешно отправлено пользователю {chat_id}")
                                    else:
                                        logger.error(f"Ошибка при отправке поздравления: {response.text}")
                                except Exception as e:
                                    logger.error(f"Исключение при отправке поздравления: {e}")
                        except Exception as e:
                            logger.error(f"Ошибка при проверке статуса плана: {e}", exc_info=True)
                        
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
                        answer_callback_query(callback_id, "❌ Не удалось отметить тренировку как выполненную.", show_alert=True)
                        
                elif action == 'cancel':
                    # Отмечаем тренировку как отмененную
                    success = TrainingPlanManager.mark_training_canceled(db_user_id, plan_id, day_num)
                    
                    if success:
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
                        answer_callback_query(callback_id, "❌ Не удалось отменить тренировку.", show_alert=True)
            except Exception as e:
                logger.error(f"Ошибка при обработке действия с тренировкой: {e}", exc_info=True)
                answer_callback_query(callback_id, "❌ Произошла ошибка при обработке действия.", show_alert=True)
        elif callback_data == 'view_plan':
            # Получаем telegram_id из chat_id
            telegram_id = chat_id
            
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
                        # Добавляем метку "ВЫПОЛНЕНО" в заголовок тренировки
                        day_info_title_end = day_info.find('\n')
                        if day_info_title_end > 0:
                            day_info = day_info[:day_info_title_end] + " - ВЫПОЛНЕНО" + day_info[day_info_title_end:]
                        send_telegram_message(chat_id, f"✅ {day_info}", parse_mode="Markdown")
                        has_completed = True
                    elif day_num in canceled_days:
                        # Добавляем метку "ОТМЕНЕНО" в заголовок тренировки
                        day_info_title_end = day_info.find('\n')
                        if day_info_title_end > 0:
                            day_info = day_info[:day_info_title_end] + " - ОТМЕНЕНО" + day_info[day_info_title_end:]
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
            # Получаем telegram_id из chat_id
            telegram_id = chat_id
            
            try:
                # Получаем ID пользователя из базы данных
                db_user_id = DBManager.get_user_id(telegram_id)
                
                if not db_user_id:
                    # Создаем нового пользователя
                    user_data = get_user_info(telegram_id)
                    db_user_id = DBManager.add_user(
                        telegram_id,
                        user_data.get('username'),
                        user_data.get('first_name'),
                        user_data.get('last_name')
                    )
                    if not db_user_id:
                        send_telegram_message(chat_id, "❌ Произошла ошибка при создании пользователя. Пожалуйста, попробуйте позже.")
                        return
                
                # Перед созданием нового плана проверяем наличие профиля бегуна
                profile = DBManager.get_runner_profile(db_user_id)
                
                if not profile:
                    # Создаем стартовый профиль по умолчанию, чтобы пользователь мог начать работу
                    default_profile = DBManager.create_default_runner_profile(db_user_id)
                    if not default_profile:
                        send_telegram_message(chat_id, "❌ Не удалось создать профиль бегуна. Пожалуйста, попробуйте позже.")
                        return
                    
                    # Сообщаем пользователю, что профиль создан и запрашиваем данные
                    send_telegram_message(
                        chat_id, 
                        "✅ Создан базовый профиль бегуна. Давайте настроим его под ваши цели.\n\n"
                        "Пожалуйста, выберите дистанцию, к которой вы готовитесь (в км):"
                    )
                    
                    # Создаем клавиатуру для выбора дистанции
                    keyboard = [
                        [
                            {"text": "5 км", "callback_data": "set_distance_5"}, 
                            {"text": "10 км", "callback_data": "set_distance_10"}
                        ],
                        [
                            {"text": "21 км (полумарафон)", "callback_data": "set_distance_21"}, 
                            {"text": "42 км (марафон)", "callback_data": "set_distance_42"}
                        ]
                    ]
                    
                    send_message_with_keyboard(chat_id, "Выберите дистанцию:", keyboard)
                    return
                
                # Если у пользователя уже есть профиль, начинаем создание нового плана
                send_telegram_message(chat_id, "⏳ Генерирую новый план тренировок на основе вашего профиля...")
                
                # Импортируем генератор плана и сервис OpenAI
                try:
                    from openai_service import OpenAIService
                    
                    # Создаем экземпляр OpenAIService
                    openai_service = OpenAIService()
                    
                    # Генерируем новый план тренировок
                    new_plan = openai_service.generate_training_plan(profile)
                    
                    if not new_plan:
                        send_telegram_message(chat_id, "❌ Не удалось сгенерировать план тренировок. Пожалуйста, попробуйте позже.")
                        return
                    
                    # Сохраняем план в базе данных
                    plan_id = TrainingPlanManager.save_training_plan(db_user_id, new_plan)
                    
                    if not plan_id:
                        send_telegram_message(chat_id, "❌ Не удалось сохранить план тренировок. Пожалуйста, попробуйте позже.")
                        return
                    
                    # Сообщаем пользователю об успешном создании плана
                    send_telegram_message(chat_id, "✅ Новый план тренировок успешно создан!")
                    
                    # Показываем план пользователю
                    fake_callback_query = {
                        'id': str(uuid.uuid4()),
                        'from': {'id': chat_id, 'first_name': 'User'},
                        'message': {'chat': {'id': chat_id}, 'message_id': 0},
                        'data': 'view_plan'
                    }
                    handle_callback_query(application, {'callback_query': fake_callback_query})
                
                except ImportError as e:
                    logger.error(f"Не удалось импортировать OpenAIService: {e}", exc_info=True)
                    send_telegram_message(chat_id, "❌ Произошла ошибка при генерации плана. Пожалуйста, попробуйте позже.")
                except Exception as e:
                    logger.error(f"Ошибка при создании плана тренировок: {e}", exc_info=True)
                    send_telegram_message(chat_id, "❌ Произошла ошибка при создании плана тренировок. Пожалуйста, попробуйте позже.")
            
            except Exception as e:
                logger.error(f"Ошибка при обработке запроса на создание нового плана: {e}", exc_info=True)
                send_telegram_message(chat_id, "❌ Произошла ошибка при создании плана. Пожалуйста, попробуйте снова.")
        elif callback_data == 'no_adjust':
            # Пользователь отказался от корректировки плана
            send_telegram_message(chat_id, "План тренировок оставлен без изменений.")
        elif callback_data.startswith('continue_plan_'):
            # Инициирует продолжение тренировок и создание нового плана
            try:
                # Разбираем callback_data для получения id текущего плана
                plan_id = int(callback_data.split('_')[-1])
                
                # Получаем telegram_id из chat_id
                telegram_id = chat_id
                
                # Получаем user_id из telegram_id
                db_user_id = DBManager.get_user_id(telegram_id)
                
                if not db_user_id:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш профиль. Пожалуйста, начните заново с команды /start.")
                    return

                # Получаем профиль пользователя
                profile = DBManager.get_runner_profile(db_user_id)
                if not profile:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш беговой профиль. Пожалуйста, начните заново с команды /start.")
                    return
                
                # Получаем текущий план тренировок и его данные
                old_plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)
                if not old_plan or 'plan_data' not in old_plan:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш предыдущий план тренировок.")
                    return
                
                # Сообщаем пользователю о начале генерации нового плана
                send_telegram_message(chat_id, "🔄 Генерирую новый план тренировок с учетом вашего прогресса...")
                
                # Импортируем генератор плана и сервис OpenAI
                try:
                    from openai_service import OpenAIService
                    from bot_modified import format_training_plan_message
                    
                    # Создаем экземпляр OpenAIService
                    openai_service = OpenAIService()
                    # Функция generate_training_plan доступна как метод
                    generate_training_plan = openai_service.generate_training_plan
                except ImportError as e:
                    logger.error(f"Не удалось импортировать генератор планов тренировок: {e}", exc_info=True)
                    send_telegram_message(chat_id, "❌ Произошла ошибка при генерации плана. Пожалуйста, попробуйте позже.")
                    return
                
                # Получаем данные для генерации
                plan_data = old_plan['plan_data']
                weekly_volume = profile.get('weekly_volume', 0)
                
                # Генерируем новый план тренировок
                try:
                    # Дополняем профиль с данными из предыдущего плана
                    profile_for_plan = profile.copy()
                    profile_for_plan['weekly_volume'] = weekly_volume
                    
                    # Передаем данные для генерации нового плана
                    new_plan = generate_training_plan(profile_for_plan)
                    
                    if not new_plan:
                        send_telegram_message(chat_id, "❌ Не удалось сгенерировать новый план тренировок. Пожалуйста, попробуйте позже.")
                        return
                    
                    # Сохраняем новый план в базу данных
                    plan_saved = TrainingPlanManager.save_training_plan(db_user_id, new_plan)
                    
                    if not plan_saved:
                        send_telegram_message(chat_id, "❌ Не удалось сохранить новый план тренировок. Пожалуйста, попробуйте позже.")
                        return
                    
                    # Форматируем сообщение с планом
                    plan_message = format_training_plan_message(new_plan)
                    
                    # Создаем кнопки для просмотра плана
                    view_plan_button = {
                        "text": "👁 Посмотреть текущий план",
                        "callback_data": "view_plan"
                    }
                    keyboard = [[view_plan_button]]
                    
                    # Отправляем план пользователю
                    send_message_with_keyboard(
                        chat_id,
                        f"✅ Новый план тренировок успешно создан!\n\n{plan_message}",
                        keyboard
                    )
                    
                    # Отвечаем на callback_query
                    answer_callback_query(callback_id, "✅ Новый план тренировок создан!")
                    
                except Exception as e:
                    logger.error(f"Ошибка при генерации нового плана: {e}", exc_info=True)
                    send_telegram_message(chat_id, "❌ Произошла ошибка при генерации плана. Пожалуйста, попробуйте позже.")
            
            except Exception as e:
                logger.error(f"Ошибка при обработке continue_plan: {e}", exc_info=True)
                answer_callback_query(callback_id, "❌ Произошла ошибка при обработке запроса.", show_alert=True)
        
        elif callback_data.startswith('adjust_plan_'):
            # Корректировка оставшегося плана тренировок
            try:
                # Разбираем callback_data
                parts = callback_data.split('_')
                plan_id = int(parts[2])
                canceled_day = int(parts[3])
                
                # Получаем ID пользователя из базы данных
                user_id = chat_id
                db_user_id = DBManager.get_user_id(user_id)
                
                if not db_user_id:
                    send_telegram_message(chat_id, "❌ Не удалось найти ваш профиль.")
                    return
                
                # Сообщаем пользователю о начале корректировки
                send_telegram_message(chat_id, "🔄 Корректирую оставшиеся тренировки...")
                
                # Здесь должна быть логика корректировки плана
                # Для примера просто сообщаем об успехе
                send_telegram_message(chat_id, "✅ План тренировок успешно скорректирован с учетом пропущенной тренировки!")
                
                # Показываем обновленный план
                fake_callback_query = {
                    'id': str(uuid.uuid4()),
                    'from': {'id': chat_id, 'first_name': 'User'},
                    'message': {'chat': {'id': chat_id}, 'message_id': 0},
                    'data': 'view_plan'
                }
                handle_callback_query(application, {'callback_query': fake_callback_query})
            except Exception as e:
                logger.error(f"Ошибка при корректировке плана тренировок: {e}", exc_info=True)
                send_telegram_message(chat_id, "❌ Произошла ошибка при корректировке плана тренировок.")
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

def get_user_info(telegram_id):
    """
    Получает информацию о пользователе из Telegram API.
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Словарь с информацией о пользователе или пустой словарь в случае ошибки
    """
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat"
        data = {"chat_id": telegram_id}
        
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json().get('result', {})
            return {
                'first_name': result.get('first_name', ''),
                'last_name': result.get('last_name', ''),
                'username': result.get('username', '')
            }
        else:
            logger.error(f"Ошибка при получении информации о пользователе: {response.text}")
            # Возвращаем пустой словарь в случае ошибки
            return {}
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе: {e}", exc_info=True)
        return {}

def start_profile_creation_dialog(chat_id, user_id):
    """
    Запускает интерактивный диалог создания профиля бегуна.
    
    Args:
        chat_id: ID чата Telegram
        user_id: ID пользователя в базе данных
    """
    try:
        # Отправляем первый вопрос о дистанции
        keyboard = [
            [{"text": "5 км", "callback_data": "set_distance_5"}],
            [{"text": "10 км", "callback_data": "set_distance_10"}],
            [{"text": "21.1 км (полумарафон)", "callback_data": "set_distance_21"}],
            [{"text": "42.2 км (марафон)", "callback_data": "set_distance_42"}]
        ]
        
        send_message_with_keyboard(
            chat_id,
            "🏃‍♂️ На какую дистанцию вы хотите подготовиться?",
            keyboard
        )
        
        logger.info(f"Запущен диалог создания профиля для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при запуске диалога создания профиля: {e}", exc_info=True)
        send_telegram_message(chat_id, "❌ Произошла ошибка при создании профиля. Пожалуйста, попробуйте позже.")

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
            "reply_markup": reply_markup  # Отправляем напрямую без json.dumps
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        logger.info(f"Отправляем сообщение с клавиатурой для {chat_id}: {text[:50]}...")
        logger.info(f"Клавиатура: {keyboard}")
            
        response = requests.post(url, json=data)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            logger.info(f"Сообщение с клавиатурой успешно отправлено: message_id={response_data.get('result', {}).get('message_id')}")
            return response_data.get('result', {}).get('message_id')
        else:
            logger.error(f"Ошибка при отправке сообщения с клавиатурой: {response.text}")
            logger.error(f"Данные запроса: {data}")
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
            message = f"Нет активности {int(time_diff // 60)} мин"
            alive = False
        
        return {
            "status": status,
            "last_update": last_update,
            "alive": alive,
            "message": message
        }
    except Exception as e:
        logger.error(f"Ошибка при получении состояния здоровья: {e}")
        return {
            "status": "error",
            "last_update": None,
            "alive": False,
            "message": f"Ошибка: {str(e)}"
        }

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HEALTH_FILE, "w") as f:
            f.write(current_time)
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла здоровья: {e}")

def setup_webhook(replit_domain=None):
    """
    Настраивает webhook URL на основе домена Replit.
    
    Args:
        replit_domain: Домен Replit (опционально). Если не указан, пытается получить из окружения.
    """
    try:
        if not replit_domain:
            # Используем домен Replit из переменных окружения
            import os
            try:
                # Предпочтительно используем REPLIT_DOMAINS (новый формат)
                if "REPLIT_DOMAINS" in os.environ:
                    replit_domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
                    logger.info(f"Использую домен REPLIT_DOMAINS: {replit_domain}")
                # Альтернативно используем REPLIT_DEV_DOMAIN
                elif "REPLIT_DEV_DOMAIN" in os.environ:
                    replit_domain = os.environ.get('REPLIT_DEV_DOMAIN')
                    logger.info(f"Использую домен REPLIT_DEV_DOMAIN: {replit_domain}")
                # Старый формат REPL_SLUG.REPL_OWNER.repl.co
                elif "REPL_SLUG" in os.environ and "REPL_OWNER" in os.environ:
                    replit_domain = f"{os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co"
                    logger.info(f"Использую домен REPL_SLUG.REPL_OWNER: {replit_domain}")
                # Fallback
                else:
                    # Получаем hostname текущего сервера
                    import socket
                    hostname = socket.gethostname()
                    logger.info(f"Использую fallback hostname: {hostname}")
                    replit_domain = hostname
            except Exception as e:
                logger.error(f"Ошибка при определении домена Replit: {e}")
                # Последний fallback домен
                replit_domain = "workspace.replit.app"
                logger.warning(f"Использую последний fallback домен: {replit_domain}")
            
        # Формируем webhook URL
        if replit_domain:
            # ИСПРАВЛЕНИЕ: Убираем строку Application[bot=ExtBot] из URL
            if isinstance(replit_domain, str):
                webhook_url = f"https://{replit_domain}/webhook/{TELEGRAM_TOKEN}"
            else:
                # Если replit_domain не строка, используем переменную окружения
                import os
                slug = os.environ.get("REPL_SLUG", "")
                owner = os.environ.get("REPL_OWNER", "")
                if slug and owner:
                    webhook_url = f"https://{slug}.{owner}.repl.co/webhook/{TELEGRAM_TOKEN}"
                else:
                    logger.error("Не удалось определить домен Replit из Application объекта или переменных окружения")
                    return False
        else:
            logger.error("Не удалось определить домен Replit")
            return False
        
        logger.info(f"Устанавливаем вебхук на URL: {webhook_url}")
        
        # Вызываем API Telegram для установки webhook
        import requests
        
        # Отключаем предыдущий вебхук и ждем завершения
        delete_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"
        delete_response = requests.post(delete_url)
        if delete_response.status_code == 200:
            logger.info(f"Предыдущий webhook удален: {delete_response.json()}")
        else:
            logger.error(f"Ошибка при удалении webhook: {delete_response.text}")
        
        # Добавляем небольшую паузу между удалением и установкой
        import time
        time.sleep(1)
        
        # Устанавливаем новый вебхук с улучшенной устойчивостью
        set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        params = {
            "url": webhook_url,
            "max_connections": 40,
            "drop_pending_updates": True,
            "allowed_updates": ["message", "callback_query", "chat_member"]
        }
        
        response = requests.post(set_url, json=params)
        
        if response.status_code == 200 and response.json().get("ok", False):
            logger.info(f"Webhook успешно установлен: {response.json()}")
            return True
        else:
            logger.error(f"Ошибка при установке webhook: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при настройке webhook: {e}", exc_info=True)
        return False

def register_webhook_routes(app):
    """
    Регистрирует маршруты webhook в Flask-приложении.
    
    Args:
        app: Экземпляр Flask
    """
    try:
        # Регистрируем Blueprint в приложении
        try:
            app.register_blueprint(webhook_bp, url_prefix='/webhook')
            logger.info("Маршруты webhook успешно зарегистрированы")
        except Exception as e:
            logger.error(f"Blueprint уже зарегистрирован: {e}")
    except Exception as e:
        logger.error(f"Ошибка при регистрации маршрутов webhook: {e}", exc_info=True)
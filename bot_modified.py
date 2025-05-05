import os
import json
import io
import traceback
import logging
from datetime import datetime, timedelta
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, 
    MessageHandler, filters, TypeHandler
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, Update

from config import TELEGRAM_TOKEN, logging, STATES
from models import create_tables
from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from openai_service import OpenAIService
from conversation import RunnerProfileConversation
from image_analyzer import ImageAnalyzer


def format_weekly_volume(volume, default_value="0"):
    """
    Форматирует значение еженедельного объема бега, избегая отображения None.
    
    Args:
        volume: Текущее значение объема
        default_value: Значение по умолчанию, если текущее значение None или "None"
        
    Returns:
        Отформатированная строка с объемом бега
    """
    if volume is None or volume == "None" or not volume:
        return f"{default_value} км/неделю"
    
    # Если в строке уже содержится единица измерения, возвращаем как есть
    if isinstance(volume, str) and ("км/неделю" in volume or "км" in volume):
        return volume
    
    # Иначе добавляем единицу измерения
    return f"{volume} км/неделю"

async def help_command(update, context):
    """Handler for the /help command."""
    # Добавим проверку работы часовых поясов
    from datetime import datetime, timedelta
    import pytz
    
    # Получим текущее время в UTC
    utc_now = datetime.now(pytz.UTC)
    
    # Преобразуем в московское время
    moscow_tz = pytz.timezone('Europe/Moscow')
    moscow_now = utc_now.astimezone(moscow_tz)
    
    # Логирование и отображение времени для отладки
    logging.info(f"Текущее время (UTC): {utc_now.strftime('%d.%m.%Y %H:%M:%S')}")
    logging.info(f"Текущее время (Москва): {moscow_now.strftime('%d.%m.%Y %H:%M:%S')}")
    
    # Генерируем даты для следующих 7 дней
    dates = []
    for i in range(7):
        date = moscow_now + timedelta(days=i)
        dates.append(date.strftime("%d.%m.%Y"))
    
    logging.info(f"Сгенерированные даты для трейнингов: {dates}")
    
    help_text = (
        "👋 Привет! Я бот-помощник для бегунов. Вот что я могу:\n\n"
        "/plan - Создать или просмотреть план тренировок\n"
        "/pending - Показать только незавершенные тренировки\n"
        "/help - Показать это сообщение с командами\n\n"
        "📱 Вы также можете отправить мне скриншот из вашего трекера тренировок (Nike Run, Strava, Garmin и др.), "
        "и я автоматически проанализирую его и зачту вашу тренировку!\n\n"
        "Для начала работы и создания персонализированного плана тренировок, "
        "используйте команду /plan\n\n"
        f"Текущая дата и время (Москва): {moscow_now.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"Даты для тренировок: {', '.join(dates[:3])}..."
    )
    await update.message.reply_text(help_text)

async def pending_trainings_command(update, context):
    """Handler for the /pending command - shows only pending (not completed) trainings."""
    try:
        # Get user ID from database
        telegram_id = update.effective_user.id
        db_user_id = DBManager.get_user_id(telegram_id)
        
        if not db_user_id:
            # User not found, prompt to start a conversation
            await update.message.reply_text(
                "⚠️ Чтобы создать план тренировок, сначала нужно создать профиль бегуна. "
                "Используйте команду /plan и выберите 'Создать новый'."
            )
            return
        
        # Get latest training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        if not plan:
            await update.message.reply_text(
                "❌ У вас еще нет плана тренировок. Используйте команду /plan для его создания."
            )
            return
        
        # Get completed and canceled trainings
        plan_id = plan['id']
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
        
        # Send plan overview
        await update.message.reply_text(
            f"✅ Ваш персонализированный план тренировок:\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )
        
        # Send only not completed or canceled training days
        has_pending_trainings = False
        for idx, day in enumerate(plan['plan_data']['training_days']):
            training_day_num = idx + 1
            
            # Skip completed and canceled training days
            if training_day_num in processed_days:
                continue
                
            has_pending_trainings = True
            
            day_message = (
                f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )
            
            # Create "Выполнено" and "Отменить" buttons for each training day
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
            ])
            
            await update.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
            
        # If all trainings are completed or canceled, show a congratulation message with continue button
        if not has_pending_trainings:
            # Calculate total completed distance
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
            
            # Add total distance to user profile
            new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)
            
            # Format the weekly volume
            formatted_volume = format_weekly_volume(new_volume, str(total_distance))
            
            # Create continue button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
            ])
            
            await update.message.reply_text(
                f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
                f"Хотите продолжить тренировки с учетом вашего прогресса?",
                reply_markup=keyboard
            )
    
    except Exception as e:
        logging.error(f"Error generating training plan: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
        )

async def generate_plan_command(update, context):
    """Handler for the /plan command."""
    try:
        # Get user ID from database
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        
        # Try to add/update user and get the ID
        db_user_id = DBManager.add_user(telegram_id, username, first_name, last_name)
        
        if not db_user_id:
            await update.message.reply_text("❌ Произошла ошибка при регистрации пользователя.")
            return
        
        # Check if user has a runner profile
        profile = DBManager.get_runner_profile(db_user_id)
        
        if not profile:
            # User doesn't have a profile yet, suggest to create one
            await update.message.reply_text(
                "⚠️ У вас еще нет профиля бегуна. Давайте создадим его!\n\n"
                "Для начала сбора данных, введите /plan"
            )
            return
        
        # Check if user already has a training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        
        if plan:
            # User already has a plan, ask if they want to view it or create a new one
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ Посмотреть текущий план", callback_data="view_plan")],
                [InlineKeyboardButton("🆕 Создать новый план", callback_data="new_plan")]
            ])
            
            await update.message.reply_text(
                "У вас уже есть план тренировок. Что вы хотите сделать?",
                reply_markup=keyboard
            )
            return
        
        # Generate new training plan
        await update.message.reply_text("⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...")
        
        # Get OpenAI service and generate plan
        openai_service = OpenAIService()
        plan = openai_service.generate_training_plan(profile)
        
        # Save the plan to database
        plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)
        
        if not plan_id:
            await update.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
            return
        
        # Send plan overview with info about screenshot uploads
        await update.message.reply_text(
            f"✅ Ваш персонализированный план тренировок готов!\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}\n\n"
            f"📱 Совет: вы можете просто присылать мне скриншоты из вашего трекера тренировок "
            f"(Nike Run, Strava, Garmin и др.), и я автоматически проанализирую результаты "
            f"и зачту вашу тренировку!",
            parse_mode='Markdown'
        )
        
        # Send each training day with action buttons
        for idx, day in enumerate(plan['training_days']):
            training_day_num = idx + 1
            day_message = (
                f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )
            
            # Create "Выполнено" and "Отменить" buttons for each training day
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
            ])
            
            await update.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        logging.error(f"Error generating training plan: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
        )

async def callback_query_handler(update, context):
    """Handler for inline button callbacks."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    db_user_id = DBManager.get_user_id(telegram_id)
    
    # Обработка кнопки выполнения тренировки
    if query.data.startswith('complete_'):
        # Формат: complete_PLAN_ID_DAY_NUMBER
        try:
            _, plan_id, day_number = query.data.split('_')
            plan_id = int(plan_id)
            day_number = int(day_number)
            
            # Отмечаем тренировку как выполненную
            success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, day_number)
            
            if success:
                # Получаем план снова, чтобы увидеть обновленные отметки о выполнении
                plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                if not plan:
                    await query.message.reply_text("❌ Не удалось найти план тренировок.")
                    return
                
                # Получаем день тренировки
                day_idx = day_number - 1
                if day_idx < 0 or day_idx >= len(plan['plan_data']['training_days']):
                    await query.message.reply_text("❌ Неверный номер тренировки.")
                    return
                
                day = plan['plan_data']['training_days'][day_idx]
                
                # Обновляем сообщение с отметкой о выполнении
                day_message = (
                    f"✅ *День {day_number}: {day['day']} ({day['date']})* - ВЫПОЛНЕНО\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )
                
                try:
                    # Пытаемся обновить сообщение, если это возможно
                    await query.message.edit_text(day_message, parse_mode='Markdown')
                except Exception:
                    # Если не удается обновить, отправляем новое сообщение
                    await query.message.reply_text(
                        f"✅ Тренировка на день {day_number} отмечена как выполненная!"
                    )
                
                # Проверяем, все ли тренировки выполнены или отменены
                completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
                processed_days = completed_days + canceled_days
                
                # Количество тренировок в плане
                total_days = len(plan['plan_data']['training_days'])
                
                # Проверка, все ли тренировки выполнены или отменены
                has_pending_trainings = any(day_num not in processed_days for day_num in range(1, total_days + 1))
                
                # Если все тренировки выполнены или отменены, отправляем поздравительное сообщение
                if not has_pending_trainings:
                    # Расчет общего пройденного расстояния
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
                    
                    # Обновление еженедельного объема в профиле пользователя
                    new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)
                    
                    # Форматирование объема бега для отображения
                    formatted_volume = format_weekly_volume(new_volume, str(total_distance))
                    
                    # Создание кнопки для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])
                    
                    # Отправка сообщения пользователю
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.reply_text("❌ Не удалось отметить тренировку как выполненную.")
                
        except Exception as e:
            logging.error(f"Error marking training as completed: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")
            
    # Обработка кнопки отмены тренировки
    elif query.data.startswith('cancel_'):
        # Формат: cancel_PLAN_ID_DAY_NUMBER
        try:
            _, plan_id, day_number = query.data.split('_')
            plan_id = int(plan_id)
            day_number = int(day_number)
            
            # Отмечаем тренировку как отмененную
            success = TrainingPlanManager.mark_training_canceled(db_user_id, plan_id, day_number)
            
            if success:
                # Получаем план снова, чтобы увидеть обновленные отметки
                plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                if not plan:
                    await query.message.reply_text("❌ Не удалось найти план тренировок.")
                    return
                
                # Получаем день тренировки
                day_idx = day_number - 1
                if day_idx < 0 or day_idx >= len(plan['plan_data']['training_days']):
                    await query.message.reply_text("❌ Неверный номер тренировки.")
                    return
                
                day = plan['plan_data']['training_days'][day_idx]
                
                # Обновляем сообщение с отметкой об отмене
                day_message = (
                    f"❌ *День {day_number}: {day['day']} ({day['date']})* - ОТМЕНЕНО\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )
                
                try:
                    # Пытаемся обновить сообщение, если это возможно
                    await query.message.edit_text(day_message, parse_mode='Markdown')
                except Exception:
                    # Если не удается обновить, отправляем новое сообщение
                    await query.message.reply_text(
                        f"❌ Тренировка на день {day_number} отмечена как отмененная!"
                    )
                
                # Проверяем, все ли тренировки выполнены или отменены
                completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
                processed_days = completed_days + canceled_days
                
                # Количество тренировок в плане
                total_days = len(plan['plan_data']['training_days'])
                
                # Проверка, все ли тренировки выполнены или отменены
                has_pending_trainings = any(day_num not in processed_days for day_num in range(1, total_days + 1))
                
                # Предлагаем скорректировать план, если это не последняя тренировка
                if has_pending_trainings:
                    # Получаем профиль бегуна для возможной корректировки плана
                    runner_profile = DBManager.get_runner_profile(db_user_id)
                    if runner_profile:
                        # Создаем кнопки для корректировки плана или продолжения без изменений
                        # Используем единый формат для всех кнопок корректировки плана
                        adjust_callback = f"adjust_plan_{plan_id}_{day_number}_0_0"  # Используем тот же формат, что и везде, с нулями вместо расстояний
                        logging.info(f"Создаем кнопку с callback_data: {adjust_callback}")
                        
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("📋 Скорректировать план", callback_data=adjust_callback)],
                            [InlineKeyboardButton("✅ Продолжить без изменений", callback_data="no_adjustment")]
                        ])
                        
                        # Отправляем сообщение с предложением скорректировать план
                        await query.message.reply_text(
                            f"❓ Хотите скорректировать оставшиеся тренировки после отмены тренировки дня {day_number}?\n\n"
                            f"Это поможет перераспределить нагрузку и сохранить баланс в вашем тренировочном плане.",
                            reply_markup=keyboard
                        )
                    
                # Если все тренировки выполнены или отменены, отправляем поздравительное сообщение
                if not has_pending_trainings:
                    # Расчет общего пройденного расстояния
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
                    
                    # Обновление еженедельного объема в профиле пользователя
                    new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)
                    
                    # Форматирование объема бега для отображения
                    formatted_volume = format_weekly_volume(new_volume, str(total_distance))
                    
                    # Создание кнопки для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])
                    
                    # Отправка сообщения пользователю
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.reply_text("❌ Не удалось отметить тренировку как отмененную.")
                
        except Exception as e:
            logging.error(f"Error marking training as canceled: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")
            
    # Обработка кнопки "Посмотреть текущий план"
    elif query.data == "view_plan":
        try:
            # Получаем последний план пользователя
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            
            if not plan:
                await query.message.reply_text("❌ У вас нет активного плана тренировок.")
                return
            
            # Получаем выполненные и отмененные тренировки
            plan_id = plan['id']
            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            
            # Отправляем общую информацию о плане
            await query.message.reply_text(
                f"✅ Ваш персонализированный план тренировок:\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Отправляем каждый день тренировки с соответствующими кнопками
            # Проверяем структуру данных плана и выбираем правильное поле
            training_days = []
            
            # Подробное логирование для отладки
            logging.info(f"План для пользователя: {db_user_id}, ID плана: {plan.get('id', 'Нет ID')}")
            logging.info(f"Ключи в плане: {list(plan.keys())}")
            
            if 'training_days' in plan:
                logging.info("Найдены дни тренировок в корне плана")
                training_days = plan['training_days']
            elif 'plan_data' in plan:
                logging.info(f"Найдено поле plan_data, тип: {type(plan['plan_data'])}")
                if isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                    logging.info("Найдены дни тренировок в plan_data")
                    training_days = plan['plan_data']['training_days']
                elif isinstance(plan['plan_data'], str):
                    # Если plan_data - это строка JSON, пробуем распарсить
                    try:
                        plan_data_json = json.loads(plan['plan_data'])
                        if 'training_days' in plan_data_json:
                            logging.info("Найдены дни тренировок после парсинга JSON")
                            training_days = plan_data_json['training_days']
                    except:
                        logging.error("Не удалось распарсить plan_data как JSON")
            
            logging.info(f"Найдено дней тренировок: {len(training_days) if training_days else 0}")
            
            for idx, day in enumerate(training_days):
                training_day_num = idx + 1
                
                # Проверяем, выполнена ли тренировка
                day_completed = training_day_num in completed_days
                day_canceled = training_day_num in canceled_days
                
                # Формируем сообщение в зависимости от статуса
                if day_completed:
                    day_message = (
                        f"✅ *День {training_day_num}: {day['day']} ({day['date']})* - ВЫПОЛНЕНО\n"
                        f"Тип: {day['training_type']}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    await query.message.reply_text(day_message, parse_mode='Markdown')
                elif day_canceled:
                    day_message = (
                        f"❌ *День {training_day_num}: {day['day']} ({day['date']})* - ОТМЕНЕНО\n"
                        f"Тип: {day['training_type']}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    await query.message.reply_text(day_message, parse_mode='Markdown')
                else:
                    day_message = (
                        f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {day['training_type']}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    
                    # Добавляем кнопки для действий
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                    ])
                    
                    await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
            
        except Exception as e:
            logging.error(f"Error viewing training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при просмотре плана тренировок.")
            
    # Обработка кнопки "Создать новый план"
    elif query.data == "new_plan":
        try:
            # Получаем профиль пользователя
            profile = DBManager.get_runner_profile(db_user_id)
            
            if not profile:
                # Инициируем сбор данных о пользователе
                await query.message.reply_text(
                    "Для создания персонализированного плана тренировок мне нужно собрать некоторую информацию о вас. "
                    "Давайте начнем с основных данных."
                )
                
                # Создаем и запускаем обработчик диалога
                conversation = RunnerProfileConversation()
                conversation_handler = conversation.get_conversation_handler()
                context.application.add_handler(conversation_handler)
                
                # Запускаем диалог
                await conversation.start(update, context)
                return
            
            # Получаем последний план пользователя
            current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            
            if not current_plan:
                # Если нет текущего плана, генерируем новый план с нуля
                with open("attached_assets/котик.jpeg", "rb") as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\ Твой котик всегда готов к любой задаче! 🐱💪"
                    )
                
                # Получаем сервис OpenAI и генерируем план
                openai_service = OpenAIService()
                plan = openai_service.generate_training_plan(profile)
            else:
                # Если есть текущий план, создаем его продолжение
                plan_id = current_plan['id']
                # Проверяем, есть ли завершенные тренировки
                completed_trainings = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                
                # Расчет общего пройденного расстояния
                total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id) 
                
                # Добавляем логирование для отладки
                logging.info(f"Вычисленная дистанция: {total_distance:.1f} км")
                
                # Убедимся, что дистанция не может быть отрицательной или нулевой
                if total_distance <= 0:
                    # Перепроверим расчет дистанции напрямую из плана
                    try:
                        # Получаем завершенные дни для текущего плана
                        completed_training_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                        
                        recalculated_distance = 0
                        for day_num in completed_training_days:
                            day_idx = day_num - 1
                            # Определяем правильную структуру плана
                            training_days = []
                            if 'training_days' in current_plan:
                                training_days = current_plan['training_days']
                            elif 'plan_data' in current_plan and isinstance(current_plan['plan_data'], dict) and 'training_days' in current_plan['plan_data']:
                                training_days = current_plan['plan_data']['training_days']
                            
                            if day_idx < 0 or day_idx >= len(training_days):
                                continue
                            
                            day_data = training_days[day_idx]
                            distance_str = day_data.get('distance', '0 км').split()[0]
                            try:
                                distance = float(distance_str)
                                recalculated_distance += distance
                            except (ValueError, TypeError):
                                pass
                        
                        if recalculated_distance > 0:
                            total_distance = recalculated_distance
                            logging.info(f"Пересчитали дистанцию: {total_distance:.1f} км")
                    except Exception as e:
                        logging.error(f"Ошибка при перерасчете дистанции: {e}")
                
                # Убедимся, что прогресс не может быть меньше или равен нулю
                progress_display = f" с учетом вашего прогресса ({total_distance:.1f} км)"
                if total_distance <= 0:
                    progress_display = ""
                
                with open("attached_assets/котик.jpeg", "rb") as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption=f"⏳ Генерирую продолжение плана тренировок{progress_display}. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                    )
                
                # Получаем сервис OpenAI и генерируем продолжение плана
                openai_service = OpenAIService()
                
                # Определяем правильную структуру данных для плана
                plan_data_for_api = current_plan
                if 'plan_data' in current_plan and isinstance(current_plan['plan_data'], dict):
                    plan_data_for_api = current_plan['plan_data']
                
                plan = openai_service.generate_training_plan_continuation(profile, total_distance, plan_data_for_api)
            
            # Сохраняем план в базу данных
            plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)
            
            if not plan_id:
                await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                return
            
            # Отправляем общую информацию о плане
            await query.message.reply_text(
                f"✅ Ваш персонализированный план тренировок готов!\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Отправляем каждый день тренировки с соответствующими кнопками
            for idx, day in enumerate(plan['training_days']):
                training_day_num = idx + 1
                day_message = (
                    f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )
                
                # Создаем кнопки для действий
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                ])
                
                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
                
        except Exception as e:
            logging.error(f"Error creating new training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при создании нового плана тренировок.")
            
    # Обработка кнопки "Подготовить план тренировок"
    elif query.data == "generate_plan":
        try:
            # Получаем данные пользователя
            telegram_id = update.effective_user.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name
            
            # Пытаемся добавить/обновить пользователя и получить ID
            db_user_id = DBManager.add_user(telegram_id, username, first_name, last_name)
            
            if not db_user_id:
                await query.message.reply_text("❌ Произошла ошибка при регистрации пользователя.")
                return
            
            # Проверяем, есть ли у пользователя профиль бегуна
            profile = DBManager.get_runner_profile(db_user_id)
            
            if not profile:
                # У пользователя нет профиля, предлагаем создать
                await query.message.reply_text(
                    "⚠️ У вас еще нет профиля бегуна. Давайте создадим его!\n\n"
                    "Для начала сбора данных, введите /plan"
                )
                return
            
            # Получаем последний план пользователя
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            
            if plan:
                # У пользователя уже есть план, спрашиваем, что он хочет сделать
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👁️ Посмотреть текущий план", callback_data="view_plan")],
                    [InlineKeyboardButton("🆕 Создать новый план", callback_data="new_plan")]
                ])
                
                await query.message.reply_text(
                    "У вас уже есть план тренировок. Что вы хотите сделать?",
                    reply_markup=keyboard
                )
                return
            
            # Генерируем новый план тренировок и отправляем сообщение с котиком
            with open("attached_assets/котик.jpeg", "rb") as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                )
            
            # Получаем сервис OpenAI и генерируем план
            openai_service = OpenAIService()
            plan = openai_service.generate_training_plan(profile)
            
            # Сохраняем план в базу данных
            plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)
            
            if not plan_id:
                await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                return
            
            # Отправляем общую информацию о плане
            await query.message.reply_text(
                f"✅ Ваш персонализированный план тренировок готов!\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Отправляем каждый день тренировки с кнопками действий
            for idx, day in enumerate(plan['training_days']):
                training_day_num = idx + 1
                day_message = (
                    f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )
                
                # Создаем кнопки "Выполнено" и "Отменить" для каждого дня тренировки
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                ])
                
                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
                
        except Exception as e:
            logging.error(f"Error generating plan from button: {e}")
            await query.message.reply_text("❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже.")
    
    # Обработка кнопки "Ни один из этих дней" при анализе скриншота тренировки
    elif query.data == "none_match":
        try:
            # Пользователь указал, что ни один день тренировки не соответствует скриншоту
            await query.message.reply_text(
                "👍 Понятно! Я отмечу это как дополнительную тренировку вне вашего плана.\n\n"
                "Хорошая работа с дополнительной активностью! Продолжайте в том же духе! 💪"
            )
        except Exception as e:
            logging.error(f"Error handling none_match button: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")
    
    # Обработка кнопки показа истории тренировок
    elif query.data.startswith("show_history_"):
        # Формат: show_history_PLAN_ID
        try:
            _, _, plan_id = query.data.split('_')
            plan_id = int(plan_id)
            
            # Получаем информацию о плане тренировок
            plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)
            if not plan:
                await query.message.reply_text("❌ Не удалось найти план тренировок.")
                return
            
            # Получаем выполненные и отмененные тренировки
            completed = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            
            # Отправляем заголовок истории тренировок
            await query.message.reply_text(
                "📜 *История тренировок:*",
                parse_mode='Markdown'
            )
            
            # Проверяем, есть ли выполненные тренировки
            if completed:
                await query.message.reply_text(
                    "✅ *Выполненные тренировки:*",
                    parse_mode='Markdown'
                )
                
                # Отправляем информацию о выполненных тренировках
                for day_num in sorted(completed):
                    # Определяем день тренировки
                    day_idx = day_num - 1
                    
                    # Определяем структуру плана
                    training_days = []
                    if 'training_days' in plan:
                        training_days = plan['training_days']
                    elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                        training_days = plan['plan_data']['training_days']
                    
                    if day_idx < 0 or day_idx >= len(training_days):
                        continue
                    
                    day = training_days[day_idx]
                    
                    # Определяем тип тренировки
                    training_type = day.get('training_type') or day.get('type', 'Не указан')
                    
                    # Формируем сообщение о дне тренировки
                    training_message = (
                        f"✅ *День {day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {training_type}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    
                    await query.message.reply_text(
                        training_message,
                        parse_mode='Markdown'
                    )
            
            # Проверяем, есть ли отмененные тренировки
            if canceled:
                await query.message.reply_text(
                    "❌ *Отмененные тренировки:*",
                    parse_mode='Markdown'
                )
                
                # Отправляем информацию об отмененных тренировках
                for day_num in sorted(canceled):
                    # Определяем день тренировки
                    day_idx = day_num - 1
                    
                    # Определяем структуру плана
                    training_days = []
                    if 'training_days' in plan:
                        training_days = plan['training_days']
                    elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                        training_days = plan['plan_data']['training_days']
                    
                    if day_idx < 0 or day_idx >= len(training_days):
                        continue
                    
                    day = training_days[day_idx]
                    
                    # Определяем тип тренировки
                    training_type = day.get('training_type') or day.get('type', 'Не указан')
                    
                    # Формируем сообщение о дне тренировки
                    training_message = (
                        f"❌ *День {day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {training_type}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    
                    await query.message.reply_text(
                        training_message,
                        parse_mode='Markdown'
                    )
            
            # Если нет ни выполненных, ни отмененных тренировок
            if not completed and not canceled:
                await query.message.reply_text(
                    "ℹ️ У вас пока нет выполненных или отмененных тренировок в этом плане."
                )
            
        except Exception as e:
            logging.error(f"Ошибка при показе истории тренировок: {e}")
            await query.message.reply_text("❌ Произошла ошибка при показе истории тренировок.")
    
    # Обработка ручного сопоставления тренировки со скриншота
    elif query.data.startswith("manual_match_"):
        try:
            # Разбираем callback data: manual_match_{plan_id}_{day_num}_{workout_distance}
            parts = query.data.split('_')
            
            # Проверяем, правильный ли формат
            if len(parts) < 5:
                await query.message.reply_text("❌ Неверный формат callback_data для ручного сопоставления.")
                return
            
            # Извлекаем параметры
            plan_id = int(parts[2])
            day_num = int(parts[3])
            workout_distance = float(parts[4])
            
            # Получаем текущий план
            plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)
            if not plan:
                await query.message.reply_text("❌ Не удалось найти указанный план тренировок.")
                return
            
            # Проверяем структуру данных плана и выбираем правильное поле для training_days
            training_days = []
            if 'training_days' in plan:
                training_days = plan['training_days']
            elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                training_days = plan['plan_data']['training_days']
            
            # Проверяем, не выходит ли day_num за пределы списка
            if day_num <= 0 or day_num > len(training_days):
                await query.message.reply_text("❌ Указан неверный номер дня тренировки.")
                return
            
            # Получаем данные о дне тренировки
            day_idx = day_num - 1
            matched_day = training_days[day_idx]
            
            # Получаем список обработанных дней
            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            processed_days = completed_days + canceled_days
            
            # Проверяем, не обработан ли уже этот день
            if day_num in processed_days:
                await query.message.reply_text(
                    f"⚠️ Тренировка за *{matched_day['date']}* уже отмечена как выполненная или отмененная.",
                    parse_mode='Markdown'
                )
                return
            
            # Отмечаем тренировку как выполненную
            success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, day_num)
            
            if success:
                # Обновляем еженедельный объем в профиле пользователя
                DBManager.update_weekly_volume(db_user_id, workout_distance)
                
                # Извлекаем запланированную дистанцию
                planned_distance = 0
                try:
                    # Извлекаем числовое значение из строки с дистанцией (напр., "5 км" -> 5)
                    import re
                    distance_match = re.search(r'(\d+(\.\d+)?)', matched_day['distance'])
                    if distance_match:
                        planned_distance = float(distance_match.group(1))
                        logging.info(f"Успешно извлечена плановая дистанция: {planned_distance} км из '{matched_day['distance']}'")
                    else:
                        logging.warning(f"Не удалось извлечь числовое значение дистанции из строки: '{matched_day['distance']}'")
                except Exception as e:
                    logging.warning(f"Error extracting planned distance: {e}")
                
                # Проверяем, значительно ли отличается фактическая дистанция от запланированной
                diff_percent = 0
                if planned_distance > 0 and workout_distance > 0:
                    diff_percent = abs(workout_distance - planned_distance) / planned_distance * 100
                    logging.info(f"Вычислена разница между фактической ({workout_distance} км) и плановой ({planned_distance} км) дистанцией: {diff_percent:.2f}%")
                
                # Формируем сообщение о сопоставлении
                training_completion_msg = (
                    f"✅ *Тренировка успешно сопоставлена с выбранным днем!*\n\n"
                    f"День {day_num}: {matched_day['day']} ({matched_day['date']})\n"
                    f"Тип: {matched_day['training_type']}\n"
                    f"Плановая дистанция: {matched_day['distance']}\n"
                    f"Фактическая дистанция: {workout_distance} км\n\n"
                )
                
                # Если разница более 20%
                if diff_percent > 20 and training_days:
                    # Добавляем сообщение о значительной разнице
                    if workout_distance > planned_distance:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% больше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план недостаточно интенсивен для вас.\n\n"
                        )
                    else:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% меньше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план слишком интенсивен для вас.\n\n"
                        )
                    
                    # Предлагаем скорректировать план
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Скорректировать план", callback_data=f"adjust_plan_{plan_id}_{day_num}_{workout_distance}_{planned_distance}")]
                    ])
                    
                    training_completion_msg += "Хотите скорректировать оставшиеся тренировки с учетом вашего фактического выполнения?"
                    
                    await query.message.edit_text(
                        training_completion_msg,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                else:
                    # Нет значительной разницы или нет оставшихся дней
                    training_completion_msg += f"Тренировка отмечена как выполненная! 👍"
                    
                    await query.message.edit_text(
                        training_completion_msg,
                        parse_mode='Markdown'
                    )
                
                # Проверяем, все ли тренировки теперь выполнены
                all_processed_days = TrainingPlanManager.get_all_processed_trainings(db_user_id, plan_id)
                if len(all_processed_days) == len(training_days):
                    # Вычисляем общую пройденную дистанцию
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
                    
                    # Создаем кнопку для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])
                    
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.edit_text(
                    "❌ Не удалось отметить тренировку как выполненную. Пожалуйста, попробуйте позже.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logging.error(f"Error handling manual match: {e}")
            await query.message.edit_text(
                "❌ Произошла ошибка при обработке ручного сопоставления. Пожалуйста, попробуйте позже."
            )
    
    # Обработка кнопки "Это дополнительная тренировка"
    elif query.data == "extra_training":
        await query.message.edit_text(
            "👍 Принято! Эта тренировка засчитана как дополнительная и не связана с текущим планом. "
            "Продолжайте следовать своему регулярному плану тренировок!"
        )
    
    # Обработка кнопки подтверждения обновления профиля
    elif query.data == "confirm_update_profile":
        try:
            # Получаем данные пользователя
            telegram_id = update.effective_user.id
            db_user_id = DBManager.get_user_id(telegram_id)
            
            if not db_user_id:
                await query.message.edit_text("❌ Ошибка: пользователь не найден в базе данных.")
                return
                
            # Удаляем текущий профиль пользователя
            # Здесь используем низкоуровневое подключение, так как DBManager не имеет метода удаления профиля
            connection = DBManager.get_connection()
            cursor = connection.cursor()
            
            try:
                cursor.execute("DELETE FROM runner_profiles WHERE user_id = %s", (db_user_id,))
                connection.commit()
                
                # Запускаем процесс создания нового профиля
                # Инициализируем класс RunnerProfileConversation
                conversation = RunnerProfileConversation()
                
                # Строим клавиатуру для выбора дистанции
                reply_markup = ReplyKeyboardMarkup(
                    [['5', '10'], ['21', '42']], 
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                
                # Отправляем сообщение о начале процесса обновления профиля
                await query.message.edit_text(
                    "✅ Ваш прежний профиль успешно удален. "
                    "Сейчас я проведу вас через процесс создания нового профиля."
                )
                
                await query.message.reply_text(
                    "Какую дистанцию бега вы планируете пробежать (в километрах)?",
                    reply_markup=reply_markup
                )
                
                # Запускаем соответствующее состояние разговора через контекст пользователя
                # Для этого добавим данные в user_data
                context.user_data['db_user_id'] = db_user_id
                context.user_data['profile_data'] = {}
                
                # Переходим в состояние DISTANCE разговора
                context.user_data['conversation_state'] = STATES['DISTANCE']
                
            except Exception as e:
                connection.rollback()
                logging.error(f"Ошибка при удалении профиля: {e}")
                await query.message.edit_text(
                    "❌ Произошла ошибка при обновлении профиля. Пожалуйста, попробуйте позже."
                )
            finally:
                cursor.close()
                connection.close()
                
        except Exception as e:
            logging.error(f"Ошибка при обработке подтверждения обновления профиля: {e}")
            await query.message.edit_text(
                "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
            )
    
    # Обработка кнопки отмены обновления профиля
    elif query.data == "cancel_update_profile":
        await query.message.edit_text(
            "✅ Обновление профиля отменено. Ваш текущий профиль остается без изменений."
        )
        
    # Обработка кнопки "adjust" - корректировка плана после отмены (устаревшая версия)
    elif query.data.startswith('adjust_') and not query.data.startswith('adjust_plan_'):
        try:
            # Этот обработчик больше не используется - все запросы перенаправляются на adjust_plan_
            logging.warning(f"【ОТЛАДКА】 Обнаружен устаревший формат adjust_. Callback: {query.data}")
            
            # Отправляем уведомление пользователю
            await query.message.reply_text(
                "⚠️ Обнаружен устаревший формат запроса на корректировку плана. "
                "Пожалуйста, используйте обновленный интерфейс для корректировки плана.\n"
                "Рекомендуется повторить последнее действие."
            )
                
        except Exception as e:
            logging.error(f"Error adjusting plan after cancellation (new format): {e}")
            await query.message.reply_text("❌ Произошла ошибка при корректировке плана тренировок.")
                
    # Обработка кнопки "adjust_after_cancel" - корректировка плана после отмены (устаревшая версия)
    elif query.data.startswith('adjust_after_cancel_'):
        try:
            # Этот обработчик больше не используется - все запросы перенаправляются на adjust_plan_
            logging.warning(f"【ОТЛАДКА】 Обнаружен устаревший формат adjust_after_cancel_. Callback: {query.data}")
            
            # Отправляем уведомление пользователю
            await query.message.reply_text(
                "⚠️ Обнаружен устаревший формат запроса на корректировку плана. "
                "Пожалуйста, используйте обновленный интерфейс для корректировки плана.\n"
                "Рекомендуется повторить последнее действие через меню /pending или /help."
            )
                
        except Exception as e:
            logging.error(f"Error adjusting plan after cancellation: {e}")
            await query.message.reply_text("❌ Произошла ошибка при корректировке плана тренировок.")
            
    # Обработка кнопки "no_adjustment" - продолжить без корректировки
    elif query.data == "no_adjustment":
        try:
            await query.message.reply_text("✅ Вы решили продолжить без корректировки плана.")
        except Exception as e:
            logging.error(f"Error handling no_adjustment: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")
    
    # Обработка кнопки корректировки плана
    elif query.data.startswith("adjust_plan_"):
        try:
            logging.info(f"===== НАЖАТА КНОПКА КОРРЕКТИРОВКИ ПЛАНА =====")
            logging.info(f"Пользователь: {update.effective_user.username} (ID: {update.effective_user.id})")
            logging.info(f"Callback data: {query.data}")
            
            # Извлекаем параметры из callback_data
            # Формат: adjust_plan_PLAN_ID_DAY_NUMBER_ACTUAL_DISTANCE_PLANNED_DISTANCE
            parts = query.data.split('_')
            
            if len(parts) < 6:
                await query.message.reply_text("❌ Некорректный формат данных для корректировки плана.")
                return
                
            try:
                plan_id = int(parts[2])
                day_number = int(parts[3])
                actual_distance = float(parts[4])
                planned_distance = float(parts[5])
                
                logging.info(f"Извлеченные параметры: plan_id={plan_id}, day_number={day_number}, actual_distance={actual_distance}, planned_distance={planned_distance}")
            except (ValueError, IndexError) as e:
                logging.error(f"Ошибка при обработке параметров callback: {e}")
                await query.message.reply_text("❌ Некорректные данные в запросе корректировки плана.")
                return
            
            # Получаем профиль бегуна
            profile = DBManager.get_runner_profile(db_user_id)
            if not profile:
                await query.message.reply_text("❌ Не удалось найти профиль бегуна.")
                return
                
            # Получаем план тренировок
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            if not plan or plan['id'] != plan_id:
                await query.message.reply_text("❌ Не удалось найти указанный план тренировок.")
                return
            
            # Отправляем сообщение о начале корректировки
            processing_message = await query.message.reply_text(
                "⏳ Разрабатываем скорректированный план тренировок...\n"
                "Это может занять некоторое время, пожалуйста, подождите."
            )
            
            # Расчет разницы между запланированной и фактической дистанциями
            diff_percent = ((actual_distance - planned_distance) / planned_distance) * 100
            logging.info(f"Разница между фактической и плановой дистанцией: {diff_percent:.1f}%")
            
            # Корректируем план с помощью OpenAI
            openai_service = OpenAIService()
            adjusted_plan = openai_service.adjust_plan_after_difference(
                profile, 
                plan['plan_data'], 
                day_number,
                actual_distance,
                planned_distance,
                diff_percent
            )
            
            if not adjusted_plan:
                await processing_message.edit_text("❌ Не удалось скорректировать план тренировок.")
                return
                
            # Обновляем план в базе данных
            success = TrainingPlanManager.update_training_plan(
                db_user_id, 
                plan_id, 
                adjusted_plan
            )
            
            if success:
                await processing_message.edit_text(
                    "✅ План тренировок успешно скорректирован!\n\n"
                    f"Оставшиеся тренировки были адаптированы с учетом вашего фактического выполнения "
                    f"({actual_distance} км вместо запланированных {planned_distance} км)."
                )
                
                # Отправляем обновленный план
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👁 Посмотреть обновленный план", callback_data="view_plan")]
                ])
                
                await query.message.reply_text(
                    "📋 Ваш план тренировок был скорректирован. Вы можете посмотреть обновленные тренировки:",
                    reply_markup=keyboard
                )
            else:
                await processing_message.edit_text("❌ Не удалось обновить план тренировок в базе данных.")
                
        except Exception as e:
            logging.error(f"Error adjusting plan: {e}")
            logging.error(traceback.format_exc())
            await query.message.reply_text("❌ Произошла ошибка при корректировке плана.")
    
    # Обработка кнопки "Продолжить тренировки"
    elif query.data.startswith('continue_plan_'):
        # Формат: continue_plan_PLAN_ID
        try:
            _, _, plan_id = query.data.split('_')
            plan_id = int(plan_id)
            
            # Получение данных пользователя
            telegram_id = update.effective_user.id
            username = update.effective_user.username
            
            # Логируем информацию о пользователе для отладки
            logging.info(f"Пользователь: {username} (ID: {telegram_id}), db_user_id: {db_user_id}")
            logging.info(f"Пытаемся продолжить план {plan_id}")
            
            # Если профиль не найден, попробуем пересоздать его
            profile = DBManager.get_runner_profile(db_user_id)
            
            if not profile:
                logging.warning(f"Профиль бегуна для пользователя {username} (ID: {telegram_id}) не найден")
                
                # Проверяем, возможно нужно заново получить db_user_id
                db_user_id_check = DBManager.get_user_id(telegram_id)
                logging.info(f"Проверка db_user_id: {db_user_id_check}")
                
                if db_user_id_check and db_user_id_check != db_user_id:
                    db_user_id = db_user_id_check
                    profile = DBManager.get_runner_profile(db_user_id)
                    
                # Если профиль всё еще не найден, попробуем создать профиль по умолчанию
                if not profile:
                    logging.info(f"Creating default profile for user: {username} (ID: {telegram_id})")
                    try:
                        # Создание профиля по умолчанию
                        profile = DBManager.create_default_runner_profile(db_user_id)
                        
                        if profile:
                            logging.info(f"Default profile created successfully for {username}")
                            await query.message.reply_text(
                                "⚠️ Нам не удалось найти ваш оригинальный профиль, но мы создали для вас базовый профиль, "
                                "чтобы продолжить тренировки.\n\n"
                                "Вы всегда можете обновить свои данные через команду /plan"
                            )
                        else:
                            # Если не удалось создать профиль, предлагаем пользователю создать его самостоятельно
                            logging.warning(f"Failed to create default profile for {username}")
                            await query.message.reply_text(
                                "❌ Не удалось найти профиль бегуна. Похоже, данные вашего профиля были потеряны.\n\n"
                                "Пожалуйста, создайте новый профиль с помощью команды /plan"
                            )
                            return
                    except Exception as e:
                        logging.error(f"Error creating default profile: {e}")
                        await query.message.reply_text(
                            "❌ Произошла ошибка при попытке восстановить ваш профиль.\n\n"
                            "Пожалуйста, создайте новый профиль с помощью команды /plan"
                        )
                        return
            
            # Получаем текущий план
            current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            if not current_plan or current_plan['id'] != plan_id:
                await query.message.reply_text("❌ Не удалось найти указанный план тренировок.")
                return
            
            # Расчет общего пройденного расстояния
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
            
            # Сообщаем пользователю о начале генерации нового плана
            with open("attached_assets/котик.jpeg", "rb") as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=f"⏳ Генерирую продолжение плана тренировок с учетом вашего прогресса ({total_distance:.1f} км). Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                )
            
            # Получаем сервис OpenAI и генерируем продолжение плана
            try:
                logging.info("Инициализация OpenAIService для продолжения плана")
                openai_service = OpenAIService()
                
                logging.info(f"Вызов generate_training_plan_continuation с параметрами: profile_id={profile['id']}, total_distance={total_distance}")
                new_plan = openai_service.generate_training_plan_continuation(profile, total_distance, current_plan['plan_data'])
                logging.info(f"Получен новый план: {new_plan.get('plan_name', 'Неизвестный план')}")
                
                # Сохраняем новый план в базу данных
                logging.info(f"Сохранение нового плана в БД для пользователя {db_user_id}")
                new_plan_id = TrainingPlanManager.save_training_plan(db_user_id, new_plan)
                logging.info(f"Новый план сохранен с ID: {new_plan_id}")
            except Exception as e:
                logging.error(f"Ошибка при генерации или сохранении плана: {e}")
                await query.message.reply_text(
                    "❌ Произошла ошибка при генерации нового плана тренировок. Пожалуйста, попробуйте позже."
                )
                return
            
            if not new_plan_id:
                await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                return
            
            # Отправляем общую информацию о плане
            await query.message.reply_text(
                f"✅ Ваш новый план тренировок готов!\n\n"
                f"*{new_plan['plan_name']}*\n\n"
                f"{new_plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Отправляем каждый день тренировки с соответствующими кнопками
            for idx, day in enumerate(new_plan['training_days']):
                training_day_num = idx + 1
                day_message = (
                    f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )
                
                # Создаем кнопки для действий
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{new_plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{new_plan_id}_{training_day_num}")]
                ])
                
                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
                
        except Exception as e:
            logging.error(f"Error continuing training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при создании продолжения плана тренировок.")
            
async def handle_photo(update, context):
    """Handler for photo messages to analyze workout screenshots."""
    try:
        # Get user information
        telegram_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        first_name = update.effective_user.first_name or "Unknown"
        
        # Log the photo reception
        logging.info(f"Received photo from {username} (ID: {telegram_id})")
        
        # Check if user exists in database
        db_user_id = DBManager.get_user_id(telegram_id)
        if not db_user_id:
            # User not found, prompt to create a profile
            await update.message.reply_text(
                "⚠️ Для анализа тренировки сначала нужно создать профиль бегуна. "
                "Используйте команду /plan для создания профиля."
            )
            return
        
        # Check if user has an active training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        if not plan:
            await update.message.reply_text(
                "❌ У вас еще нет плана тренировок. Используйте команду /plan для его создания."
            )
            return
        
        # Send processing message
        processing_message = await update.message.reply_text(
            "🔍 Анализирую ваш скриншот тренировки... Это может занять некоторое время."
        )
        
        # Get photo with best quality
        photo = update.message.photo[-1]
        
        # Download the photo
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Analyze the screenshot
        analyzer = ImageAnalyzer()
        workout_data = analyzer.analyze_workout_screenshot(photo_bytes)
        
        # Log the analysis results in detail
        logging.info(f"Детальный анализ скриншота тренировки: {workout_data}")
        
        # Отдельно логируем важные поля для отладки
        if "дистанция_км" in workout_data:
            logging.info(f"Обнаружена дистанция: {workout_data['дистанция_км']} км")
        else:
            logging.warning("Дистанция не обнаружена в скриншоте!")
            
        if "дата" in workout_data:
            logging.info(f"Обнаружена дата тренировки: {workout_data['дата']}")
        else:
            logging.warning("Дата не обнаружена в скриншоте!")
        
        # Check if analysis was successful
        if 'error' in workout_data:
            await update.message.reply_text(
                f"❌ Не удалось проанализировать скриншот: {workout_data['error']}\n\n"
                "Пожалуйста, убедитесь, что скриншот содержит информацию о тренировке и попробуйте снова."
            )
            return
        
        # Get training plan data
        plan_id = plan['id']
        training_days = plan['plan_data']['training_days']
        
        # Get processed training days
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
           
        # Check if this is a running workout or another type of workout
        workout_type = workout_data.get("тип_тренировки", "").lower()
        
        # Check common running workout types in Russian and English
        running_types = ["бег", "пробежка", "run", "running", "jogging", "бег трусцой"]
        is_running_workout = any(run_type in workout_type for run_type in running_types) if workout_type else True
        
        if workout_type and not is_running_workout:
            # Create buttons for marking training as completed manually
            buttons = []
            for idx, day in enumerate(training_days):
                day_num = idx + 1
                if day_num not in processed_days:
                    buttons.append([InlineKeyboardButton(
                        f"День {day_num}: {day['day']} ({day['date']}) - {day['distance']}",
                        callback_data=f"complete_{plan_id}_{day_num}"
                    )])
                    
            # Only add buttons if we have some unprocessed days
            if buttons:
                keyboard = InlineKeyboardMarkup(buttons)
                
                await update.message.reply_text(
                    f"⚠️ Обнаружена тренировка типа *{workout_type}*!\n\n"
                    f"В данный момент я могу обрабатывать только беговые тренировки. "
                    f"Поддержка других типов тренировок (плавание, велосипед, силовые и т.д.) "
                    f"будет добавлена в ближайшее время.\n\n"
                    f"Вы можете загрузить скриншот беговой тренировки или выбрать день тренировки, "
                    f"который хотите отметить как выполненный:",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Обнаружена тренировка типа *{workout_type}*!\n\n"
                    f"В данный момент я могу обрабатывать только беговые тренировки. "
                    f"Поддержка других типов тренировок (плавание, велосипед, силовые и т.д.) "
                    f"будет добавлена в ближайшее время.\n\n"
                    f"Пожалуйста, загрузите скриншот беговой тренировки.",
                    parse_mode='Markdown'
                )
            return
        
        # Получаем данные даты из скриншота для правильного сопоставления
        workout_date_str = workout_data.get("дата", "")
        # Преобразуем дату "DD.MM.YYYY" в объект datetime для сравнения
        workout_date_obj = None
        if workout_date_str:
            try:
                # Пробуем стандартный российский формат
                workout_date_obj = datetime.strptime(workout_date_str, "%d.%m.%Y")
                logging.info(f"Получена дата тренировки из скриншота: {workout_date_obj.strftime('%Y-%m-%d')}")
            except ValueError:
                # Пробуем другие форматы (например, американский "April 27, 2025")
                try:
                    # Извлекаем дату из строки в формате "4/27/25 - 11:17 AM"
                    import re
                    date_match = re.search(r'(\d+)/(\d+)/(\d+)', workout_date_str)
                    if date_match:
                        month, day, year = map(int, date_match.groups())
                        # Предполагаем, что это 20xx год
                        if year < 100:
                            year += 2000
                        workout_date_obj = datetime(year, month, day)
                        logging.info(f"Получена дата тренировки из скриншота (альтернативный формат): {workout_date_obj.strftime('%Y-%m-%d')}")
                except Exception as e:
                    logging.warning(f"Не удалось распознать дату из '{workout_date_str}': {e}")
        
        # Устанавливаем принудительное сопоставление с днем из плана по дате, если дата есть и соответствует одному из дней плана
        forced_match_idx = None
        if workout_date_obj:
            for i, day in enumerate(training_days):
                day_date_str = day.get('date', '')
                try:
                    # Преобразуем дату из плана "DD.MM.YYYY" в объект datetime
                    day_date_obj = datetime.strptime(day_date_str, "%d.%m.%Y")
                    
                    # Если даты совпадают, устанавливаем принудительное сопоставление
                    if day_date_obj.date() == workout_date_obj.date():
                        forced_match_idx = i
                        logging.info(f"Принудительное сопоставление по дате: День {i+1} ({day_date_str})")
                        break
                except ValueError:
                    logging.warning(f"Не удалось преобразовать дату '{day_date_str}' из плана.")
        
        # Если есть принудительное сопоставление по дате, используем его, иначе используем алгоритм
        if forced_match_idx is not None:
            matching_day_idx = forced_match_idx
            matching_score = 10  # Высокий балл для сопоставления по дате
            logging.info(f"Используется принудительное сопоставление по дате: День {matching_day_idx+1}")
        else:
            # Используем стандартный алгоритм сопоставления, если не удалось сопоставить по дате
            matching_day_idx, matching_score = analyzer.find_matching_training(training_days, workout_data)
        
        # Extract workout details for display
        workout_date = workout_data.get("дата", "Неизвестно")
        workout_distance = workout_data.get("дистанция_км", "Неизвестно")
        workout_time = workout_data.get("длительность", "Неизвестно")
        workout_pace = workout_data.get("темп", "Неизвестно")
        workout_app = workout_data.get("название_приложения", "Неизвестно")
        
        # Create acknowledgment message
        ack_message = (
            f"✅ Информация о тренировке успешно получена!\n\n"
            f"Дата: *{workout_date}*\n"
            f"Дистанция: *{workout_distance} км*\n"
            f"Время: *{workout_time}*\n"
            f"Темп: *{workout_pace}*\n"
            f"Источник: *{workout_app}*\n\n"
        )
        
        # Если мы нашли подходящий день тренировки с высоким рейтингом
        if matching_day_idx is not None and matching_score >= 5:
            # Get the matched training day number (1-based index)
            matched_day_num = matching_day_idx + 1
            matched_day = training_days[matching_day_idx]
            
            logging.info(f"Автоматически сопоставлен день тренировки: День {matched_day_num} ({matched_day['day']} {matched_day['date']})")
            
            # Check if this training day is already processed
            if matched_day_num in processed_days:
                await update.message.reply_text(
                    f"{ack_message}⚠️ Тренировка за *{matched_day['date']}* уже отмечена как выполненная или отмененная.",
                    parse_mode='Markdown'
                )
                return
            
            # Mark training as completed
            success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, matched_day_num)
            
            if success:
                # Update weekly volume in profile (add completed distance)
                try:
                    distance_km = float(workout_distance)
                    DBManager.update_weekly_volume(db_user_id, distance_km)
                except (ValueError, TypeError):
                    logging.warning(f"Could not update weekly volume with distance: {workout_distance}")
                
                # Extract planned distance
                planned_distance = 0
                try:
                    # Extract numeric value from distance string (e.g., "5 км" -> 5)
                    import re
                    distance_match = re.search(r'(\d+(\.\d+)?)', matched_day['distance'])
                    if distance_match:
                        planned_distance = float(distance_match.group(1))
                        logging.info(f"Успешно извлечена плановая дистанция: {planned_distance} км из '{matched_day['distance']}'")
                    else:
                        logging.warning(f"Не удалось извлечь числовое значение дистанции из строки: '{matched_day['distance']}'")
                except Exception as e:
                    logging.warning(f"Error extracting planned distance: {e}")
                
                # Check if actual distance significantly differs from planned distance
                try:
                    actual_distance = float(workout_distance)
                    logging.info(f"Преобразована фактическая дистанция в число: {actual_distance} км")
                except ValueError as e:
                    logging.error(f"Ошибка преобразования фактической дистанции '{workout_distance}' в число: {e}")
                    actual_distance = 0
                
                diff_percent = 0
                if planned_distance > 0 and actual_distance >= 0:
                    # Обычный случай - рассчитываем процентную разницу
                    diff_percent = abs(actual_distance - planned_distance) / planned_distance * 100
                    logging.info(f"Вычислена разница между фактической ({actual_distance} км) и плановой ({planned_distance} км) дистанцией: {diff_percent:.2f}%")
                elif planned_distance == 0 and actual_distance > 0:
                    # Особый случай - день отдыха (0 км), но пользователь всё равно бегал
                    # Устанавливаем разницу 100%, чтобы сработало условие корректировки плана
                    diff_percent = 100.0
                    logging.info(f"Особый случай: плановая дистанция 0 км, но фактическая {actual_distance} км. Устанавливаем diff_percent = 100%")
                
                # Create the acknowledgment message
                training_completion_msg = (
                    f"{ack_message}🎉 Тренировка успешно сопоставлена с планом!\n\n"
                    f"День {matched_day_num}: {matched_day['day']} ({matched_day['date']})\n"
                    f"Тип: {matched_day['training_type']}\n"
                    f"Плановая дистанция: {matched_day['distance']}\n"
                    f"Фактическая дистанция: {workout_distance} км\n\n"
                )
                
                # Логируем текущее условие для определения ошибки
                logging.info(f"Проверка условия корректировки плана: diff_percent={diff_percent}, training_days_exists={bool(training_days)}, remaining_days={len(training_days) > matched_day_num}")
                
                # If difference is more than 20%
                # Проверяем, что: 
                # 1) разница больше 20%
                # 2) есть training_days
                # 3) проверяем остались ли дни в плане (для логики отображения кнопок)
                # Всегда предлагаем корректировку плана, если разница > 20%
                remaining_days = len([day_num for day_num in range(1, len(training_days) + 1) if day_num > matched_day_num and day_num not in processed_days])
                is_last_day = (matched_day_num == len(training_days))
                logging.info(f"Оставшиеся необработанные дни в плане: {remaining_days}, это последний день: {is_last_day}, разница в дистанциях: {diff_percent:.2f}%")
                
                if diff_percent > 20 and training_days:
                    # Add a message about the significant difference
                    if planned_distance == 0 and actual_distance > 0:
                        training_completion_msg += (
                            f"⚠️ Вы бегали {actual_distance} км в день, запланированный как отдых (0 км)!\n"
                            f"Это может повлиять на ваше восстановление и общую эффективность тренировок.\n\n"
                        )
                    elif actual_distance > planned_distance:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% больше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план недостаточно интенсивен для вас.\n\n"
                        )
                    else:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% меньше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план слишком интенсивен для вас.\n\n"
                        )
                    
                    # Проверяем, является ли это последним днем плана
                    if is_last_day:
                        # Если это последний день плана, предлагаем создать новый план
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Создать новый план", callback_data=f"continue_plan_{plan_id}")]
                        ])
                        
                        training_completion_msg += "Это последний день вашего плана. Хотите создать новый план с учетом ваших фактических результатов?"
                    else:
                        # Иначе предлагаем скорректировать существующий план
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("📝 Скорректировать план", callback_data=f"adjust_plan_{plan_id}_{matched_day_num}_{actual_distance}_{planned_distance}")]
                        ])
                        
                        training_completion_msg += "Хотите скорректировать оставшиеся тренировки с учетом вашего фактического выполнения?"
                    
                    await update.message.reply_text(
                        training_completion_msg,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                else:
                    # No significant difference or no remaining days
                    training_completion_msg += f"Тренировка отмечена как выполненная! 👍"
                    
                    await update.message.reply_text(
                        training_completion_msg,
                        parse_mode='Markdown'
                    )
                
                # Check if all trainings are now completed
                all_processed_days = TrainingPlanManager.get_all_processed_trainings(db_user_id, plan_id)
                if len(all_processed_days) == len(training_days):
                    # Calculate total completed distance
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
                    
                    # Create continue button
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])
                    
                    await update.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await update.message.reply_text(
                    f"{ack_message}❌ Не удалось отметить тренировку как выполненную. Пожалуйста, попробуйте сделать это вручную через /pending.",
                    parse_mode='Markdown'
                )
        else:
            # Создаем кнопки для всех непомеченных дней тренировки, чтобы пользователь мог выбрать вручную
            buttons = []
            for idx, day in enumerate(training_days):
                day_num = idx + 1
                if day_num not in processed_days:
                    buttons.append([InlineKeyboardButton(
                        f"День {day_num}: {day['day']} ({day['date']}) - {day['distance']}",
                        callback_data=f"manual_match_{plan_id}_{day_num}_{workout_distance}"
                    )])
            
            # Добавляем кнопку "Это дополнительная тренировка"
            buttons.append([InlineKeyboardButton("🏃‍♂️ Это дополнительная тренировка", callback_data="extra_training")])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(
                f"{ack_message}❓ Не удалось автоматически сопоставить эту тренировку с вашим планом.\n\n"
                f"Пожалуйста, выберите день тренировки, который хотите отметить как выполненный:",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
    except Exception as e:
        logging.error(f"Error handling photo: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при анализе фотографии. Пожалуйста, попробуйте позже или отметьте тренировку вручную через /pending."
        )


async def start_command(update, context):
    """Обработчик команды /start - начало взаимодействия с ботом."""
    user = update.effective_user
    telegram_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    
    # Добавляем пользователя в базу, если его там нет
    db_user_id = DBManager.add_user(telegram_id, username, first_name, last_name)
    
    # Получаем профиль пользователя
    profile = DBManager.get_runner_profile(db_user_id)
    
    # Формируем приветственное сообщение
    welcome_message = (
        f"👋 Привет, {first_name}!\n\n"
        "Я твой персональный помощник для подготовки к соревнованиям по бегу. "
        "Я могу создать индивидуальный план тренировок, помогу отслеживать прогресс "
        "и буду мотивировать тебя достичь твоей цели.\n\n"
    )
    
    if profile:
        # Если профиль пользователя существует, предлагаем посмотреть текущий план
        buttons = [
            ["👁️ Посмотреть текущий план"],
            ["🆕 Создать новый план"],
            ["✏️ Обновить мой профиль"]
        ]
        
        welcome_message += (
            "🔹 Используй кнопки ниже для работы с текущим планом или создания нового.\n"
            "🔹 Отправь мне скриншот из приложения для бега (Nike Run Club, Strava, Garmin), "
            "и я автоматически отмечу тренировку как выполненную.\n"
            "🔹 Используй команду /help, чтобы увидеть все доступные команды."
        )
    else:
        # Если профиля нет, предлагаем создать профиль
        buttons = [
            ["🏃‍♂️ Создать беговой профиль"]
        ]
        
        welcome_message += (
            "Для начала нам нужно создать твой беговой профиль. "
            "Нажми кнопку ниже, чтобы начать."
        )
    
    # Создаем клавиатуру и отправляем сообщение
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def log_update(update, context):
    """Логирует все входящие обновления от Telegram."""
    try:
        user = update.effective_user
        if user:
            logging.info(f"Получено обновление от пользователя {user.id} (@{user.username}) - {user.first_name} {user.last_name}")
        
        # Логируем тип обновления
        if update.message:
            if update.message.text:
                logging.info(f"Текстовое сообщение: {update.message.text}")
            elif update.message.photo:
                logging.info(f"Получена фотография")
            else:
                logging.info(f"Другой тип сообщения: {update.message}")
        elif update.callback_query:
            logging.info(f"Callback запрос: {update.callback_query.data}")
        else:
            logging.info(f"Другой тип обновления: {update}")
        
        # Передаем обновление дальше в цепочку обработчиков
        return False
    except Exception as e:
        logging.error(f"Ошибка в логировании обновления: {e}")
        return False

def setup_bot():
    """Configure and return the bot application."""
    # Create the Application object
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Create database tables if they don't exist
    create_tables()
    
    # Добавляем логирование всех входящих обновлений перед любыми обработчиками
    application.add_handler(TypeHandler(Update, log_update), group=-1)  # Группа -1 выполняется первой
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CommandHandler("pending", pending_trainings_command))
    
    # Add conversation handler for profile creation
    conversation = RunnerProfileConversation()
    application.add_handler(conversation.get_conversation_handler())
    
    # Add photo handler for analyzing workout screenshots
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Add text message handler for button responses
    async def text_message_handler(update, context):
        """Обработчик текстовых сообщений от пользователя."""
        text = update.message.text.strip()
        user = update.effective_user
        telegram_id = user.id
        
        # Получаем ID пользователя в БД
        db_user_id = DBManager.get_user_id(telegram_id)
        
        if not db_user_id:
            await update.message.reply_text(
                "Пожалуйста, используйте команду /start, чтобы начать работу с ботом."
            )
            return
        
        # Обрабатываем различные текстовые команды от кнопок
        if text == "👁️ Посмотреть текущий план":
            # Перенаправляем на обработку команды просмотра плана
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            
            if not plan:
                await update.message.reply_text(
                    "У вас еще нет плана тренировок. Создайте его командой /plan"
                )
                return
                
            # Получаем обработанные тренировки
            completed = TrainingPlanManager.get_completed_trainings(db_user_id, plan['id'])
            canceled = TrainingPlanManager.get_canceled_trainings(db_user_id, plan['id'])
            processed_days = completed + canceled  # Все обработанные дни
            
            # Отправляем общую информацию о плане
            await update.message.reply_text(
                f"✅ Ваш персонализированный план тренировок:\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Проверяем, есть ли предстоящие тренировки
            has_pending_trainings = False
            total_training_days = len(plan['plan_data']['training_days'])
            
            # Считаем количество предстоящих тренировок
            pending_count = total_training_days - len(processed_days)
            
            # Если есть предстоящие тренировки, отправляем сначала их
            if pending_count > 0:
                await update.message.reply_text(
                    "📆 *Предстоящие тренировки:*",
                    parse_mode='Markdown'
                )
                
                # Отправляем только предстоящие дни тренировок
                pending_shown = False
                for idx, day in enumerate(plan['plan_data']['training_days']):
                    training_day_num = idx + 1
                    
                    # Пропускаем обработанные тренировки
                    if training_day_num in processed_days:
                        continue
                    
                    pending_shown = True
                    
                    # Определяем поле с типом тренировки (может быть 'type' или 'training_type')
                    training_type = day.get('training_type') or day.get('type', 'Не указан')
                    
                    training_message = (
                        f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {training_type}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    
                    # Добавляем кнопки для предстоящих тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", 
                                          callback_data=f"complete_{plan['id']}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", 
                                          callback_data=f"cancel_{plan['id']}_{training_day_num}")]
                    ])
                    
                    await update.message.reply_text(
                        training_message,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                
                # На случай, если что-то пошло не так и у нас нет предстоящих тренировок
                if not pending_shown:
                    await update.message.reply_text(
                        "⚠️ Не удалось найти предстоящие тренировки, хотя они должны быть. "
                        "Это может быть ошибкой в данных."
                    )
            
            # Если есть завершенные или отмененные тренировки, показываем их после предстоящих
            if completed or canceled:
                # Создаем кнопку для отображения истории тренировок
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📜 Показать историю тренировок", 
                                      callback_data=f"show_history_{plan['id']}")]
                ])
                
                # Информация о прогрессе
                total_completed_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan['id'])
                
                await update.message.reply_text(
                    f"📊 *Статистика плана:*\n\n"
                    f"Всего тренировок: {total_training_days}\n"
                    f"Выполнено: {len(completed)}\n"
                    f"Отменено: {len(canceled)}\n"
                    f"Осталось: {pending_count}\n"
                    f"Пройдено километров: {total_completed_distance:.1f} км",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            
            # Если все тренировки выполнены или отменены, предлагаем продолжить тренировки
            if pending_count == 0:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Продолжить тренировки", 
                                      callback_data=f"continue_plan_{plan['id']}")]
                ])
                
                await update.message.reply_text(
                    "🎉 Все тренировки в текущем плане выполнены или отменены! "
                    "Хотите продолжить тренировки с учетом вашего прогресса?",
                    reply_markup=keyboard
                )
                
        elif text == "🆕 Создать новый план":
            # Отправляем сообщение с котиком
            with open("attached_assets/котик.jpeg", "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                )
            
            # Генерируем новый план
            try:
                # Получаем профиль пользователя
                profile = DBManager.get_runner_profile(db_user_id)
                
                if not profile:
                    await update.message.reply_text(
                        "⚠️ У вас еще нет профиля бегуна. Используйте команду /start, чтобы создать его."
                    )
                    return
                
                # Инициализируем сервис OpenAI
                openai_service = OpenAIService()
                
                # Генерируем план
                plan = openai_service.generate_training_plan(profile)
                
                # Сохраняем план в БД
                plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)
                
                if not plan_id:
                    await update.message.reply_text(
                        "❌ Произошла ошибка при сохранении плана тренировок."
                    )
                    return
                
                # Получаем сохраненный план
                saved_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                
                # Отправляем план пользователю
                await update.message.reply_text(
                    f"✅ Ваш персонализированный план тренировок готов!\n\n"
                    f"*{saved_plan['plan_name']}*\n\n"
                    f"{saved_plan['plan_description']}",
                    parse_mode='Markdown'
                )
                
                # Отправляем дни тренировок
                # Определяем структуру плана
                training_days = []
                if 'training_days' in saved_plan:
                    training_days = saved_plan['training_days']
                elif 'plan_data' in saved_plan and isinstance(saved_plan['plan_data'], dict) and 'training_days' in saved_plan['plan_data']:
                    training_days = saved_plan['plan_data']['training_days']
                else:
                    logging.error(f"Неверная структура плана: {saved_plan.keys()}")
                    await update.message.reply_text("❌ Ошибка в структуре плана тренировок.")
                    return
                
                for idx, day in enumerate(training_days):
                    training_day_num = idx + 1
                    
                    # Создаем сообщение с днем тренировки
                    # Определяем поле с типом тренировки (может быть 'type' или 'training_type')
                    training_type = day.get('training_type') or day.get('type', 'Не указан')
                    
                    training_message = (
                        f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {training_type}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )
                    
                    # Добавляем кнопки
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", 
                                             callback_data=f"complete_{saved_plan['id']}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", 
                                             callback_data=f"cancel_{saved_plan['id']}_{training_day_num}")]
                    ])
                    
                    await update.message.reply_text(
                        training_message,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                logging.error(f"Ошибка генерации плана: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
                )
                
        elif text == "✏️ Обновить мой профиль":
            # Выводим предупреждение и предлагаем подтвердить обновление профиля
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, обновить профиль", callback_data="confirm_update_profile")],
                [InlineKeyboardButton("❌ Нет, оставить текущий", callback_data="cancel_update_profile")]
            ])
            
            await update.message.reply_text(
                "⚠️ *Внимание!* Вы собираетесь обновить свой беговой профиль.\n\n"
                "Все текущие данные будут удалены, и вам нужно будет заново указать "
                "дистанцию, дату соревнований, возраст, рост, вес и другие параметры.\n\n"
                "Ваш текущий план тренировок останется без изменений.\n\n"
                "Вы уверены, что хотите продолжить?",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    return application
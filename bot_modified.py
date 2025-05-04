import os
import json
import io
from datetime import datetime, timedelta
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from config import TELEGRAM_TOKEN, logging
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
            if 'training_days' in plan:
                training_days = plan['training_days']
            elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                training_days = plan['plan_data']['training_days']
            
            logging.info(f"План для пользователя: {db_user_id}, структура: {plan.keys()}")
            logging.info(f"Найдено дней тренировок: {len(training_days)}")
            
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
                        caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
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
    
    # Обработка кнопки корректировки плана
    elif query.data.startswith("adjust_plan_"):
        try:
            # Разбираем callback data: adjust_plan_{plan_id}_{day_num}_{actual_distance}_{planned_distance}
            parts = query.data.split('_')
            
            # Проверяем, правильный ли формат
            if len(parts) < 6:
                await query.message.reply_text("❌ Неверный формат callback_data для корректировки плана.")
                return
            
            # Извлекаем параметры
            plan_id = int(parts[2])
            day_num = int(parts[3])
            actual_distance = float(parts[4])
            planned_distance = float(parts[5])
            
            # Получаем профиль бегуна
            runner_profile = DBManager.get_runner_profile(db_user_id)
            if not runner_profile:
                await query.message.reply_text("❌ Не удалось получить профиль бегуна.")
                return
            
            # Получаем текущий план
            current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            if not current_plan or current_plan['id'] != plan_id:
                await query.message.reply_text("❌ Не удалось найти указанный план тренировок.")
                return
            
            # Отправляем сообщение о начале корректировки
            await query.message.reply_text(
                "🔄 Корректирую ваш план тренировок с учетом фактического выполнения...\n"
                "Это может занять некоторое время."
            )
            
            # Создаем инстанс OpenAI сервиса и корректируем план
            openai_service = OpenAIService()
            adjusted_plan = openai_service.adjust_training_plan(
                runner_profile,
                current_plan['plan_data'],
                day_num,
                planned_distance,
                actual_distance
            )
            
            if not adjusted_plan:
                await query.message.reply_text("❌ Не удалось скорректировать план. Пожалуйста, попробуйте позже.")
                return
            
            # Обновляем план в базе данных
            success = TrainingPlanManager.update_training_plan(db_user_id, plan_id, adjusted_plan)
            
            if not success:
                await query.message.reply_text("❌ Не удалось сохранить скорректированный план.")
                return
            
            # Получаем обновленный план
            updated_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            
            # Отправляем информацию о скорректированном плане
            await query.message.reply_text(
                f"✅ Ваш план тренировок успешно скорректирован!\n\n"
                f"*{updated_plan['plan_data']['plan_name']}*\n\n"
                f"{updated_plan['plan_data']['plan_description']}\n\n"
                f"📋 Вот оставшиеся дни вашего скорректированного плана:",
                parse_mode='Markdown'
            )
            
            # Получаем обработанные тренировки
            completed = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            
            # Отправляем только оставшиеся (не выполненные и не отмененные) дни тренировок
            for idx, day in enumerate(updated_plan['plan_data']['training_days']):
                training_day_num = idx + 1
                
                # Пропускаем уже обработанные дни
                if training_day_num in completed or training_day_num in canceled:
                    continue
                
                # Создаем сообщение с днем тренировки
                training_type = day.get('training_type') or day.get('type', 'Не указан')
                
                day_message = (
                    f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                    f"Тип: {training_type}\n"
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
            logging.error(f"Error adjusting plan: {e}")
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
            openai_service = OpenAIService()
            new_plan = openai_service.generate_training_plan_continuation(profile, total_distance, current_plan['plan_data'])
            
            # Сохраняем новый план в базу данных
            new_plan_id = TrainingPlanManager.save_training_plan(db_user_id, new_plan)
            
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
        
        # Log the analysis results
        logging.info(f"Workout data analysis: {workout_data}")
        
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
        
        # Find a matching training day
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
        
        # If we found a matching training day
        if matching_day_idx is not None and matching_score >= 5:
            # Get the matched training day number (1-based index)
            matched_day_num = matching_day_idx + 1
            matched_day = training_days[matching_day_idx]
            
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
                except Exception as e:
                    logging.warning(f"Error extracting planned distance: {e}")
                
                # Check if actual distance significantly differs from planned distance
                actual_distance = float(workout_distance)
                diff_percent = 0
                if planned_distance > 0:
                    diff_percent = abs(actual_distance - planned_distance) / planned_distance * 100
                
                # Create the acknowledgment message
                training_completion_msg = (
                    f"{ack_message}🎉 Тренировка успешно сопоставлена с планом!\n\n"
                    f"День {matched_day_num}: {matched_day['day']} ({matched_day['date']})\n"
                    f"Тип: {matched_day['training_type']}\n"
                    f"Плановая дистанция: {matched_day['distance']}\n"
                    f"Фактическая дистанция: {workout_distance} км\n\n"
                )
                
                # If difference is more than 20%
                if diff_percent > 20 and training_days and len(training_days) > matched_day_num:
                    # Add a message about the significant difference
                    if actual_distance > planned_distance:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% больше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план недостаточно интенсивен для вас.\n\n"
                        )
                    else:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% меньше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план слишком интенсивен для вас.\n\n"
                        )
                    
                    # Offer to adjust the plan
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
            # No matching training day found
            # Create inline buttons for all unprocessed training days
            buttons = []
            for idx, day in enumerate(training_days):
                day_num = idx + 1
                if day_num not in processed_days:
                    buttons.append([InlineKeyboardButton(
                        f"День {day_num}: {day['day']} ({day['date']}) - {day['distance']}",
                        callback_data=f"complete_{plan_id}_{day_num}"
                    )])
            
            # Add a "None of these" button
            buttons.append([InlineKeyboardButton("❌ Ни один из этих дней", callback_data="none_match")])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(
                f"{ack_message}❓ Я не смог автоматически сопоставить эту тренировку с вашим планом.\n\n"
                f"Выберите день тренировки, который соответствует этой активности, или выберите 'Ни один из этих дней', "
                f"если это была дополнительная тренировка вне плана:",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
    except Exception as e:
        logging.error(f"Error handling photo: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при анализе фотографии. Пожалуйста, попробуйте позже или отметьте тренировку вручную через /pending."
        )


def setup_bot():
    """Configure and return the bot application."""
    # Create the Application object
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Create database tables if they don't exist
    create_tables()
    
    # Add command handlers
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
            
            # Отправляем план
            await update.message.reply_text(
                f"✅ Ваш персонализированный план тренировок:\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Отправляем дни тренировок
            for idx, day in enumerate(plan['plan_data']['training_days']):
                training_day_num = idx + 1
                
                # Проверяем статус
                status = ""
                if training_day_num in completed:
                    status = "✅ "
                elif training_day_num in canceled:
                    status = "❌ "
                
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
                
                # Добавляем кнопки, если тренировка еще не обработана
                if training_day_num not in completed and training_day_num not in canceled:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", 
                                            callback_data=f"complete_{plan['id']}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", 
                                            callback_data=f"cancel_{plan['id']}_{training_day_num}")]
                    ])
                    
                    await update.message.reply_text(
                        f"{status}{training_message}",
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"{status}{training_message}",
                        parse_mode='Markdown'
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
            # Начинаем диалог обновления профиля
            await update.message.reply_text(
                "Для обновления профиля используйте команду /start. "
                "Обратите внимание, что это перезапишет ваши текущие данные."
            )
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    return application
# Импорты из python-telegram-bot
try:
    from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
except ImportError:
    # Для LSP - чтобы избежать ошибок проверки типов
    class ApplicationBuilder:
        def __init__(self, token=None): 
            self.token = token
        def build(self): 
            return None
    
    class CommandHandler:
        def __init__(self, command, callback): 
            self.command = command
            self.callback = callback
    
    class CallbackQueryHandler:
        def __init__(self, callback): 
            self.callback = callback
    
    class InlineKeyboardMarkup:
        def __init__(self, inline_keyboard): 
            self.inline_keyboard = inline_keyboard
    
    class InlineKeyboardButton:
        def __init__(self, text, callback_data=None): 
            self.text = text
            self.callback_data = callback_data
from config import TELEGRAM_TOKEN, logging
from models import create_tables
from conversation import RunnerProfileConversation
from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from openai_service import OpenAIService

async def help_command(update, context):
    """Handler for the /help command."""
    help_text = (
        "🏃‍♂️ *Помощь по Боту Профиля Бегуна* 🏃‍♀️\n\n"
        "Этот бот поможет вам создать профиль бегуна, ответив на серию вопросов.\n\n"
        "*Доступные команды:*\n"
        "/start - Начать или перезапустить процесс создания профиля\n"
        "/plan - Получить персонализированный план тренировок\n"
        "/pending - Показать только невыполненные тренировки\n"
        "/help - Показать это сообщение помощи\n"
        "/cancel - Отменить текущий разговор\n\n"
        "Во время создания профиля я задам вам вопросы о ваших беговых целях, физических параметрах "
        "и тренировочных привычках. Вы можете отменить процесс в любое время, используя команду /cancel."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def pending_trainings_command(update, context):
    """Handler for the /pending command - shows only pending (not completed) trainings."""
    try:
        # Get user ID
        telegram_id = update.effective_user.id
        db_user_id = DBManager.get_user_id(telegram_id)
        
        if not db_user_id:
            await update.message.reply_text(
                "❌ Вы еще не создали свой профиль бегуна. Используйте команду /start для создания профиля."
            )
            return
        
        # Get latest training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        
        if not plan:
            await update.message.reply_text(
                "❌ У вас еще нет плана тренировок. Используйте команду /plan для создания плана."
            )
            return
        
        # Get completed and canceled trainings
        plan_id = plan['id']
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
        
        # Get only pending trainings (not completed or canceled)
        pending_trainings = []
        for idx, day in enumerate(plan['plan_data']['training_days']):
            training_day_num = idx + 1
            if training_day_num not in processed_days:
                pending_trainings.append((training_day_num, day))
        
        if not pending_trainings:
            await update.message.reply_text(
                "🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!"
            )
            return
        
        # Send plan overview
        await update.message.reply_text(
            f"📋 *Невыполненные тренировки из плана:*\n\n"
            f"*{plan['plan_name']}*",
            parse_mode='Markdown'
        )
        
        # Send each pending training day
        for training_day_num, day in pending_trainings:
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
        logging.error(f"Error showing pending trainings: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при получении невыполненных тренировок. Пожалуйста, попробуйте позже."
        )

async def generate_plan_command(update, context):
    """Handler for the /plan command."""
    try:
        # Get user ID
        telegram_id = update.effective_user.id
        db_user_id = DBManager.get_user_id(telegram_id)
        
        if not db_user_id:
            await update.message.reply_text(
                "❌ Вы еще не создали свой профиль бегуна. Используйте команду /start для создания профиля."
            )
            return
        
        # Get runner profile
        profile = DBManager.get_runner_profile(db_user_id)
        
        if not profile:
            await update.message.reply_text(
                "❌ Профиль бегуна не найден. Используйте команду /start для создания профиля."
            )
            return
        
        # Check if plan already exists
        existing_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        
        if existing_plan:
            # Plan already exists, ask if user wants to generate a new one
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ Посмотреть существующий", callback_data="view_plan")],
                [InlineKeyboardButton("🔄 Создать новый", callback_data="new_plan")]
            ])
            
            await update.message.reply_text(
                f"У вас уже есть тренировочный план '{existing_plan['plan_name']}'. "
                f"Хотите посмотреть существующий план или создать новый?",
                reply_markup=keyboard
            )
            return
        
        # Otherwise generate a new plan
        await update.message.reply_text("⏳ Генерирую ваш персонализированный план тренировок. Это может занять некоторое время...")
        
        # Generate training plan
        openai_service = OpenAIService()
        plan = openai_service.generate_training_plan(profile)
        
        # Save plan to database
        plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)
        
        if not plan_id:
            await update.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
            return
        
        # Send plan overview
        await update.message.reply_text(
            f"✅ Ваш персонализированный план тренировок готов!\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )
        
        # Get completed and canceled trainings
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
        
        # Send only not completed training days
        has_pending_trainings = False
        for idx, day in enumerate(plan['training_days']):
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
            
            # Create continue button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
            ])
            
            await update.message.reply_text(
                f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {new_volume}.\n\n"
                f"Хотите продолжить тренировки с учетом вашего прогресса?",
                reply_markup=keyboard
            )
    
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
            else:
                await query.message.reply_text("❌ Не удалось отметить тренировку как отмененную.")
                
        except Exception as e:
            logging.error(f"Error marking training as canceled: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")
    
    elif query.data == 'view_plan':
        # Show existing plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        
        await query.message.reply_text(
            f"✅ Ваш персонализированный план тренировок:\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )
        
        # Get completed and canceled trainings
        plan_id = plan['id']
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
        
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
            
            await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
            
        # If all trainings are completed or canceled, show a congratulation message
        if not has_pending_trainings:
            await query.message.reply_text(
                "🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                "Вы можете создать новый план тренировок, используя команду /plan и выбрав 'Создать новый'."
            )
            
    elif query.data == 'new_plan' or query.data == 'generate_plan':
        # Generate new plan
        await query.message.reply_text("⏳ Генерирую новый персонализированный план тренировок. Это может занять некоторое время...")
        
        # Get runner profile
        profile = DBManager.get_runner_profile(db_user_id)
        
        # Generate new training plan
        openai_service = OpenAIService()
        plan = openai_service.generate_training_plan(profile)
        
        # Save plan to database
        plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)
        
        if not plan_id:
            await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
            return
        
        # Send plan overview
        await query.message.reply_text(
            f"✅ Ваш новый персонализированный план тренировок готов!\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )
        
        # Get completed and canceled trainings
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
            
        # Send only not completed or canceled training days
        has_pending_trainings = False
        for idx, day in enumerate(plan['training_days']):
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
            
            await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
            
        # If all trainings are completed or canceled, show a congratulation message
        if not has_pending_trainings:
            await query.message.reply_text(
                "🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                "Вы можете создать новый план тренировок, используя команду /plan и выбрав 'Создать новый'."
            )

def setup_bot():
    """Configure and return the bot application."""
    if not TELEGRAM_TOKEN:
        logging.critical("Telegram bot token is missing! Set the TELEGRAM_TOKEN environment variable.")
        raise ValueError("Telegram bot token is required")
    
    # Create database tables
    create_tables()
    
    # Initialize the bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Set up conversation handler
    conversation = RunnerProfileConversation()
    application.add_handler(conversation.get_conversation_handler())
    
    # Add standalone command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CommandHandler("pending", pending_trainings_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    return application
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
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
        "/help - Показать это сообщение помощи\n"
        "/cancel - Отменить текущий разговор\n\n"
        "Во время создания профиля я задам вам вопросы о ваших беговых целях, физических параметрах "
        "и тренировочных привычках. Вы можете отменить процесс в любое время, используя команду /cancel."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

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
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            
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
        
        # Send each training day
        for idx, day in enumerate(plan['training_days']):
            day_message = (
                f"*День {idx+1}: {day['day']}*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )
            await update.message.reply_text(day_message, parse_mode='Markdown')
    
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
    
    if query.data == 'view_plan':
        # Show existing plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        
        await query.message.reply_text(
            f"✅ Ваш персонализированный план тренировок:\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )
        
        # Send each training day
        for idx, day in enumerate(plan['plan_data']['training_days']):
            day_message = (
                f"*День {idx+1}: {day['day']}*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )
            await query.message.reply_text(day_message, parse_mode='Markdown')
            
    elif query.data == 'new_plan':
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
        
        # Send each training day
        for idx, day in enumerate(plan['training_days']):
            day_message = (
                f"*День {idx+1}: {day['day']}*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )
            await query.message.reply_text(day_message, parse_mode='Markdown')

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
    from telegram.ext import CommandHandler, CallbackQueryHandler
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    return application

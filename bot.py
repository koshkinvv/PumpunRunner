from telegram.ext import ApplicationBuilder
from config import TELEGRAM_TOKEN, logging
from models import create_tables
from conversation import RunnerProfileConversation

async def help_command(update, context):
    """Handler for the /help command."""
    help_text = (
        "🏃‍♂️ *Помощь по Боту Профиля Бегуна* 🏃‍♀️\n\n"
        "Этот бот поможет вам создать профиль бегуна, ответив на серию вопросов.\n\n"
        "*Доступные команды:*\n"
        "/start - Начать или перезапустить процесс создания профиля\n"
        "/help - Показать это сообщение помощи\n"
        "/cancel - Отменить текущий разговор\n\n"
        "Во время создания профиля я задам вам вопросы о ваших беговых целях, физических параметрах "
        "и тренировочных привычках. Вы можете отменить процесс в любое время, используя команду /cancel."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

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
    from telegram.ext import CommandHandler
    application.add_handler(CommandHandler("help", help_command))
    
    return application

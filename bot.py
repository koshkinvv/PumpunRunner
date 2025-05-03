from telegram.ext import ApplicationBuilder
from config import TELEGRAM_TOKEN, logging
from models import create_tables
from conversation import RunnerProfileConversation

async def help_command(update, context):
    """Handler for the /help command."""
    help_text = (
        "🏃‍♂️ *Runner Profile Bot Help* 🏃‍♀️\n\n"
        "This bot helps you create your runner profile by answering a series of questions.\n\n"
        "*Available commands:*\n"
        "/start - Start or restart the profile creation process\n"
        "/help - Show this help message\n"
        "/cancel - Cancel the current conversation\n\n"
        "During the profile creation, I'll ask you about your running goals, physical parameters, "
        "and training habits. You can cancel at any time using the /cancel command."
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

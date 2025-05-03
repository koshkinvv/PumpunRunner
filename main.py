import asyncio
import os
from bot import setup_bot
from config import logging
from app import app

def main():
    """Main function to start the Telegram bot."""
    try:
        # Set up and start the bot
        application = setup_bot()
        
        # Log successful startup
        logging.info("Runner profile bot started successfully!")
        
        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=["message", "callback_query"])
        
    except Exception as e:
        logging.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    # Run the main function
    main()

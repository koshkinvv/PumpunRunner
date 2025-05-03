import logging
import os
import asyncio
from bot_modified import setup_bot
from app import app  # Импортируем объект Flask app из app.py

def main():
    """Main function to start the Telegram bot."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get the bot application
    application = setup_bot()
    
    # Log startup message
    logging.info("Runner profile bot started successfully!")
    
    # Run the bot until the user sends a signal to stop it (e.g. pressing Ctrl+C)
    application.run_polling()

if __name__ == '__main__':
    main()
#!/usr/bin/env python
"""
Самый простой скрипт для запуска бота в Replit Deployments.
Использует bot.py вместо bot_modified.py
"""
from bot import setup_bot

def main():
    """Запуск бота напрямую"""
    print("Запуск бота...")
    application = setup_bot()
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
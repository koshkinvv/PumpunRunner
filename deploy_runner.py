#!/usr/bin/env python
"""
Минимальный скрипт для запуска бота в Replit Deployments.
"""
from bot_modified import setup_bot

def main():
    """Запуск бота напрямую"""
    print("Запуск бота...")
    application = setup_bot()
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
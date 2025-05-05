#!/bin/bash
# Script for running bot 24/7 on Reserved VM Replit

# Create logs directory
mkdir -p logs

# Log startup
echo "Starting 24/7 bot infrastructure..." >> logs/run_24_7.log

# Kill any existing processes
echo "Stopping all existing bot processes..." >> logs/run_24_7.log
pkill -f "python.*bot_modified.py" || true
pkill -f "python.*run_telegram_bot.py" || true
pkill -f "python.*app.py" || true
sleep 3

# Start Flask app
echo "Starting web application..." >> logs/run_24_7.log
gunicorn --bind 0.0.0.0:5000 app:app --access-logfile - --timeout 120 > logs/webapp_output.log 2>&1 &
WEBAPP_PID=$!
echo "Web app started with PID: $WEBAPP_PID" >> logs/run_24_7.log

# Start bot
echo "Starting Telegram bot..." >> logs/run_24_7.log
python main.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
echo "Bot started with PID: $BOT_PID" >> logs/run_24_7.log


# Monitor processes
while true; do
    # Check web app
    if ! ps -p $WEBAPP_PID > /dev/null; then
        echo "$(date) - Web app crashed, restarting..." >> logs/run_24_7.log
        gunicorn --bind 0.0.0.0:5000 app:app --access-logfile - --timeout 120 > logs/webapp_output.log 2>&1 &
        WEBAPP_PID=$!
    fi

    # Check bot
    if ! ps -p $BOT_PID > /dev/null; then
        echo "$(date) - Bot crashed, restarting..." >> logs/run_24_7.log
        python main.py > logs/bot_output.log 2>&1 &
        BOT_PID=$!
    fi

    #Added sync for log file flushing
    sync

    sleep 60
done
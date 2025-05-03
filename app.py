import os
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Telegram Runner Bot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
                line-height: 1.6;
            }
            .container {
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2979ff;
                margin-top: 0;
            }
            .info {
                margin-top: 20px;
                padding: 15px;
                background-color: #e3f2fd;
                border-left: 4px solid #2979ff;
                border-radius: 4px;
            }
            .status {
                font-weight: bold;
                color: #00c853;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Telegram Runner Bot</h1>
            <p>This application provides a Telegram bot for collecting runner profile information. The bot is operational and can be accessed via Telegram.</p>
            
            <div class="info">
                <p class="status">✅ Bot status: Running</p>
                <p>The Telegram bot is running and ready to accept commands. To use the bot:</p>
                <ol>
                    <li>Search for the bot on Telegram</li>
                    <li>Start a conversation with the bot by sending the <code>/start</code> command</li>
                    <li>Follow the bot's instructions to create your runner profile</li>
                </ol>
            </div>
            
            <p>The bot collects the following information:</p>
            <ul>
                <li>Running distance</li>
                <li>Competition date</li>
                <li>Personal information (gender, age, height, weight)</li>
                <li>Running experience</li>
                <li>Running goals</li>
                <li>Fitness level</li>
                <li>Weekly running volume</li>
            </ul>
        </div>
    </body>
    </html>
    """)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
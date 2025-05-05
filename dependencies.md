# Зависимости проекта

Для работы бота требуются следующие библиотеки:

```
python-telegram-bot>=20.0
openai>=1.0.0
psycopg2-binary
sqlalchemy>=2.0.0
python-dateutil>=2.8.2
pytz>=2023.0
apscheduler>=3.10.0
psutil>=5.9.0
gunicorn>=21.0.0
flask>=2.3.0
flask-sqlalchemy>=3.0.0
```

## Установка зависимостей

В Replit зависимости можно установить через Packager, или автоматически при импорте в скрипте.

### Установка в другом окружении

```bash
pip install python-telegram-bot openai psycopg2-binary sqlalchemy python-dateutil pytz apscheduler psutil gunicorn flask flask-sqlalchemy
```

## Переменные окружения

Для работы бота необходимы следующие переменные окружения:

- `TELEGRAM_TOKEN` - токен от BotFather для доступа к Telegram Bot API
- `OPENAI_API_KEY` - ключ API от OpenAI для генерации планов тренировок
- `DATABASE_URL` - URL для подключения к PostgreSQL базе данных

## Настройка базы данных

Схема базы данных создается автоматически при первом запуске бота через функцию `create_tables()` в `models.py`.
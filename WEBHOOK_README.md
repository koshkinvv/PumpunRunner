# Настройка Webhook для Telegram-бота

## Обзор системы

Для обеспечения стабильной работы бота на платформе Replit, мы реализовали механизм webhook вместо long polling. Это предотвращает "засыпание" виртуальной машины Replit при отсутствии активности и обеспечивает более надежное и быстрое получение обновлений от Telegram API.

## Компоненты системы

1. **webhook_server.py**: Основной модуль для обработки webhook-запросов от Telegram API.
2. **app.py**: Flask-приложение для мониторинга состояния бота и интеграции с webhook.
3. **main.py**: Основной скрипт запуска бота с интеграцией webhook.
4. **check_webhook.py**: Инструмент для проверки и настройки webhook.
5. **refresh_webhook.sh**: Скрипт для обновления настроек webhook при перезапуске проекта.
6. **check_webhook_availability.sh**: Скрипт для проверки доступности webhook-эндпоинта.

## Архитектура системы

1. Telegram API отправляет обновления на URL: `https://{REPLIT_DEV_DOMAIN}/webhook/{TELEGRAM_TOKEN}`
2. Flask-приложение принимает эти запросы на порту 5000
3. Обновления обрабатываются через зарегистрированный blueprint `telegram_webhook`
4. Бот обрабатывает обновления и отправляет ответы через Telegram API

## Запуск системы

Система автоматически запускается через Replit Workflows:

1. **Start application**: Запускает Flask-приложение с зарегистрированным webhook
2. **bot_runner**: Запускает бота в режиме webhook

## Мониторинг и поддержка

### Проверка статуса webhook

```bash
python check_webhook.py check
```

### Установка webhook

```bash
python check_webhook.py set
```

### Удаление webhook

```bash
python check_webhook.py delete
```

### Проверка доступности webhook

```bash
./check_webhook_availability.sh
```

### Обновление webhook при перезапуске проекта

```bash
./refresh_webhook.sh
```

## Эндпоинты

- **/webhook/{TELEGRAM_TOKEN}**: Основной эндпоинт для получения обновлений от Telegram
- **/webhook/health**: Эндпоинт для проверки состояния бота (healthcheck)

## Устранение неполадок

1. **Webhook не устанавливается**:
   - Проверьте переменную окружения `REPLIT_DEV_DOMAIN`
   - Убедитесь, что Flask-приложение запущено и слушает порт 5000

2. **Бот не отвечает на сообщения**:
   - Проверьте установку webhook: `python check_webhook.py check`
   - Проверьте доступность webhook: `./check_webhook_availability.sh`
   - Проверьте логи в папке `logs/`

3. **Конфликт портов**:
   - Если возникает ошибка `Address already in use`, убедитесь, что нет других процессов, использующих порт 5000

## Конфигурация

Настройки webhook и режима работы бота контролируются через переменные окружения в файле `.env`:

- `USE_WEBHOOK=true`: Включает режим webhook вместо polling
- `REPLIT_DEV_DOMAIN`: Домен Replit для настройки webhook URL

## Безопасность

- Webhook защищен включением токена бота в URL
- Эндпоинт health не раскрывает конфиденциальную информацию
- Webhook принимает только запросы с JSON-содержимым от Telegram API
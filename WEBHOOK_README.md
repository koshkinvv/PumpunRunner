# Настройка webhook для предотвращения "засыпания" Replit VM

Даже при использовании Reserved VM в Replit, возможны периоды "сна" для приложений, которые не получают HTTP-трафик. Эта документация описывает, как настроить webhook и мониторинг, чтобы ваш Telegram-бот работал стабильно.

## Примечание о доменах Replit

Replit автоматически создает домен для каждого проекта. Домен доступен через переменную окружения `REPLIT_DEV_DOMAIN`. 

В нашем проекте используется домен:
```
19158b70-0a3f-4963-8a92-2b91605d3479-00-1hxlsvnxqgndx.kirk.replit.dev
```

Этот домен используется для настройки webhook в Telegram API.

## Файлы и их назначение

1. **webhook_server.py** - Серверная часть для обработки webhook от Telegram
   - Содержит эндпоинты `/webhook/<TOKEN>` для приема обновлений от Telegram
   - Содержит эндпоинт `/health` для проверки работоспособности

2. **setup_webhook.py** - Скрипт для настройки webhook в Telegram API
   - Запускается отдельно: `python setup_webhook.py`
   - Настраивает webhook на URL вашего проекта в Replit

3. **keepalive.sh** - Скрипт для периодической проверки работоспособности
   - Каждые 5 минут пингует эндпоинт `/health`
   - Проверяет доступность Telegram API

4. **start_keepalive.sh** - Скрипт для запуска keepalive в фоновом режиме
   - Запускается один раз командой: `bash start_keepalive.sh`

## Как запустить

### Первичная настройка:

1. **Подготовка**:
   ```bash
   chmod +x start_keepalive.sh
   chmod +x keepalive.sh
   ```

2. **Настройка webhook**:
   ```bash
   python setup_webhook.py
   ```
   Убедитесь, что webhook успешно установлен.

3. **Запуск keepalive**:
   ```bash
   bash start_keepalive.sh
   ```
   Этот скрипт запустит `keepalive.sh` в фоновом режиме.

### Проверка работоспособности:

1. **Проверка логов keepalive**:
   ```bash
   tail -f logs/keepalive.log
   ```

2. **Проверка статуса приложения**:
   - Откройте веб-интерфейс: `https://19158b70-0a3f-4963-8a92-2b91605d3479-00-1hxlsvnxqgndx.kirk.replit.dev/`
   - Проверьте эндпоинт здоровья: `https://19158b70-0a3f-4963-8a92-2b91605d3479-00-1hxlsvnxqgndx.kirk.replit.dev/webhook/health`

3. **Проверка запущенных процессов**:
   ```bash
   ps aux | grep keepalive
   ```

### Остановка keepalive:

Если нужно остановить процесс keepalive:
```bash
pkill -f 'bash.*keepalive.sh'
```

## Важные замечания

1. Бот продолжает работать в режиме polling через `main.py`, а webhook только поддерживает активность VM.

2. Если ваш бот перестал отвечать, но keepalive продолжает работать, перезапустите бота командой:
   ```bash
   python main.py
   ```

3. Логи keepalive находятся в директории `logs/`. Регулярно проверяйте их для выявления проблем.

4. Настоятельно рекомендуется использовать Reserved VM в Replit для стабильной работы бота.
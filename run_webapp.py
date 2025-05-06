"""
Точка запуска веб-приложения в продакшн режиме.
Этот файл специально создан для запуска в Replit Deployments.
"""
import os
import logging
from gunicorn.app.base import BaseApplication
from app import app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GunicornApp(BaseApplication):
    """Класс для запуска Gunicorn с приложением Flask."""
    
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()
    
    def load_config(self):
        """Загрузка конфигурации Gunicorn."""
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)
    
    def load(self):
        """Загружает WSGI приложение."""
        return self.application

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Запуск веб-приложения на порту {port}")
    
    options = {
        'bind': f'0.0.0.0:{port}',
        'workers': 1,
        'worker_class': 'sync',
        'loglevel': 'info',
        'accesslog': '-',
        'errorlog': '-',
        'timeout': 30,
    }
    
    # Выводим список всех переменных окружения (для отладки)
    logger.info("Переменные окружения:")
    for key, value in os.environ.items():
        # Скрываем секретные значения
        if 'TOKEN' in key or 'SECRET' in key or 'PASSWORD' in key or 'KEY' in key:
            logger.info(f"  {key}: ***секретное значение***")
        else:
            logger.info(f"  {key}: {value}")
            
    try:
        # Запускаем приложение через Gunicorn
        # Сначала проверяем наличие файла шаблонов, так как это частая проблема
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        if os.path.exists(template_dir):
            logger.info(f"Директория шаблонов найдена: {template_dir}")
            template_files = os.listdir(template_dir)
            logger.info(f"Найдены шаблоны: {', '.join(template_files)}")
        else:
            logger.error(f"Директория шаблонов не найдена: {template_dir}")
            
        # Запускаем Gunicorn
        logger.info("Запуск с Gunicorn")
        GunicornApp(app, options).run()
    except Exception as e:
        # В случае ошибки запускаем через встроенный сервер Flask
        logger.error(f"Ошибка при запуске Gunicorn: {e}")
        logger.warning("Переключение на встроенный сервер Flask")
        app.run(host='0.0.0.0', port=port)
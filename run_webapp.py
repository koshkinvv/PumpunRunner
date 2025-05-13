import os
import logging
from app import app

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('webapp')

def run_webapp():
    """
    Запускает веб-приложение Flask
    """
    try:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Запуск веб-приложения на порту {port}")
        app.run(host='0.0.0.0', port=port, debug=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-приложения: {e}")
        
if __name__ == '__main__':
    run_webapp()
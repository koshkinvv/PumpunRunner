"""
WSGI entry point для Gunicorn и других WSGI серверов.
"""
from app import app as application

# Для запуска с Gunicorn
if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)

"""
WSGI-файл для запуска приложения через Gunicorn
"""

from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

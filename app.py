import os
import logging
import json
import datetime
import subprocess
import time
import psutil

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
# Создаем приложение Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "runcoach-dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Настраиваем соединение с базой данных
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# Инициализируем расширение Flask-SQLAlchemy
db.init_app(app)

# Настраиваем логгирование
logging.basicConfig(level=logging.DEBUG)

# Импортируем модели
with app.app_context():
    import models
    from db_manager import DBManager
    from training_plan_manager import TrainingPlanManager
    
    # Создаем таблицы в базе данных, если они не существуют
    db.create_all()


# Маршруты для веб-приложения
@app.route('/')
def index():
    """Главная страница лендинга"""
    return render_template('landing.html')

@app.route('/admin')
def admin():
    """Административная панель управления"""
    # Получаем статус бота
    bot_status = {
        'running': False,  # По умолчанию считаем, что бот не запущен
        'last_start': None,
        'last_error': None,
        'log': []
    }
    
    # Проверка наличия файла состояния бота
    if os.path.exists('bot_health.txt'):
        try:
            with open('bot_health.txt', 'r') as f:
                last_update = f.read().strip()
                
            # Проверяем, обновлялся ли файл в последние 30 секунд
            try:
                last_update_time = datetime.datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
                time_diff = datetime.datetime.now() - last_update_time
                if time_diff.total_seconds() < 30:
                    bot_status['running'] = True
                    bot_status['last_start'] = last_update
            except Exception as e:
                logging.error(f"Ошибка при парсинге времени: {str(e)}")
        except Exception as e:
            logging.error(f"Ошибка при чтении файла состояния бота: {str(e)}")
    
    # Получаем последние логи
    try:
        if os.path.exists('bot_monitor.log'):
            with open('bot_monitor.log', 'r') as f:
                log_lines = f.readlines()[-20:]  # Последние 20 строк
                
            for line in log_lines:
                parts = line.strip().split(' ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0] + ' ' + parts[1]
                    message = parts[2]
                    
                    # Определяем уровень лога
                    level = 'INFO'
                    if 'ERROR' in message:
                        level = 'ERROR'
                    elif 'WARNING' in message:
                        level = 'WARNING'
                    
                    bot_status['log'].append({
                        'timestamp': timestamp,
                        'level': level,
                        'message': message
                    })
    except Exception as e:
        logging.error(f"Ошибка при чтении логов: {str(e)}")
    
    # Проверяем наличие переменных окружения
    env_vars = {
        'TELEGRAM_TOKEN': bool(os.environ.get('TELEGRAM_TOKEN')),
        'DATABASE_URL': bool(os.environ.get('DATABASE_URL')),
        'OPENAI_API_KEY': bool(os.environ.get('OPENAI_API_KEY'))
    }
    
    return render_template('index.html', bot_status=bot_status, env_vars=env_vars)


@app.route('/success')
def success():
    """Страница успешной регистрации"""
    telegram_username = request.args.get('telegram')
    return render_template('success.html', telegram_username=telegram_username)


# API маршруты
@app.route('/api/check_telegram_user', methods=['POST'])
def check_telegram_user():
    """Проверяет существование пользователя Telegram в системе"""
    data = request.json
    telegram_username = data.get('telegram_username', '')
    
    if not telegram_username:
        return jsonify({'error': 'Telegram username не указан'}), 400
    
    # Нормализуем имя пользователя (убираем @ в начале, если есть)
    if telegram_username.startswith('@'):
        telegram_username = telegram_username[1:]
    
    # Проверяем наличие пользователя в базе данных
    db_manager = DBManager()
    user_exists = db_manager.check_user_exists_by_telegram(telegram_username)
    
    return jsonify({'exists': user_exists})


@app.route('/api/create_profile', methods=['POST'])
def create_profile():
    """Создает профиль бегуна и сохраняет его в базе данных"""
    try:
        data = request.json
        
        # Нормализуем имя пользователя Telegram (убираем @ в начале, если есть)
        telegram_username = data.get('telegram_username', '')
        if telegram_username.startswith('@'):
            telegram_username = telegram_username[1:]
        
        # Проверяем еще раз, нет ли уже такого пользователя
        db_manager = DBManager()
        if db_manager.check_user_exists_by_telegram(telegram_username):
            return jsonify({
                'success': False,
                'error': 'Пользователь с таким Telegram username уже существует'
            }), 400
        
        # Преобразуем предпочтительные дни тренировок в список
        preferred_days = request.json.get('preferred_days', [])
        if isinstance(preferred_days, str):
            preferred_days = [preferred_days]
        
        # Собираем данные профиля
        runner_profile = {
            'telegram_username': telegram_username,
            'goal_distance': data.get('goal_distance'),
            'goal_date': data.get('goal_date'),
            'target_time': data.get('target_time'),
            'gender': data.get('gender'),
            'age': int(data.get('age', 0)),
            'height': float(data.get('height', 0)),
            'weight': float(data.get('weight', 0)),
            'level': data.get('level'),
            'weekly_distance': float(data.get('weekly_distance', 0)),
            'comfortable_pace': data.get('comfortable_pace'),
            'training_start_date': data.get('training_start_date'),
            'training_days_per_week': int(data.get('training_days_per_week', 3)),
            'preferred_days': preferred_days
        }
        
        # Создаем пользователя и профиль бегуна
        user_id = db_manager.create_user_with_profile(runner_profile)
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'Не удалось создать профиль'
            }), 500
        
        # Записываем данные профиля в файл для возможности восстановления
        profile_filename = f"{telegram_username}_profile_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(os.path.join('data', profile_filename), 'w') as f:
            json.dump(runner_profile, f, indent=2)
        
        return jsonify({'success': True, 'user_id': user_id})
    
    except Exception as e:
        logging.error(f"Ошибка при создании профиля: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# API маршруты для управления ботом (админ-панель)
@app.route('/api/bot/status', methods=['GET'])
def bot_status():
    """Возвращает текущий статус бота"""
    status = {
        'running': False,
        'last_update': None
    }
    
    # Проверка наличия файла состояния бота
    if os.path.exists('bot_health.txt'):
        try:
            with open('bot_health.txt', 'r') as f:
                last_update = f.read().strip()
                
            # Проверяем, обновлялся ли файл в последние 30 секунд
            try:
                last_update_time = datetime.datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
                time_diff = datetime.datetime.now() - last_update_time
                if time_diff.total_seconds() < 30:
                    status['running'] = True
                    status['last_update'] = last_update
            except Exception as e:
                logging.error(f"Ошибка при парсинге времени: {str(e)}")
        except Exception as e:
            logging.error(f"Ошибка при чтении файла состояния бота: {str(e)}")
    
    return jsonify(status)


@app.route('/api/bot/logs', methods=['GET'])
def bot_logs():
    """Возвращает последние логи бота"""
    logs = []
    
    try:
        if os.path.exists('bot_monitor.log'):
            with open('bot_monitor.log', 'r') as f:
                log_lines = f.readlines()[-50:]  # Последние 50 строк
                
            for line in log_lines:
                parts = line.strip().split(' ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0] + ' ' + parts[1]
                    message = parts[2]
                    
                    # Определяем уровень лога
                    level = 'INFO'
                    if 'ERROR' in message:
                        level = 'ERROR'
                    elif 'WARNING' in message:
                        level = 'WARNING'
                    
                    logs.append({
                        'timestamp': timestamp,
                        'level': level,
                        'message': message
                    })
    except Exception as e:
        logging.error(f"Ошибка при чтении логов: {str(e)}")
    
    return jsonify({'logs': logs})


@app.route('/api/bot/start', methods=['GET'])
def start_bot():
    """Запускает бота"""
    try:
        # Используем shell скрипт для запуска бота
        script_path = os.path.abspath('bot_workflow.sh')
        subprocess.Popen(['bash', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return jsonify({'success': True, 'message': 'Бот запущен'})
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/stop', methods=['GET'])
def stop_bot():
    """Останавливает бота"""
    try:
        # Ищем и завершаем все процессы бота
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Ищем процессы Python, запущенные с файлом bot
                if proc.info['name'] == 'python' and any('bot' in arg for arg in proc.info['cmdline']):
                    processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Завершаем найденные процессы
        for proc in processes:
            proc.terminate()
        
        # Даем процессам время на корректное завершение
        if processes:
            psutil.wait_procs(processes, timeout=3)
            
            # Принудительно завершаем оставшиеся процессы
            for proc in processes:
                if proc.is_running():
                    proc.kill()
        
        # Удаляем файл состояния бота
        if os.path.exists('bot_health.txt'):
            os.remove('bot_health.txt')
            
        return jsonify({'success': True, 'message': 'Бот остановлен'})
    except Exception as e:
        logging.error(f"Ошибка при остановке бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/restart', methods=['GET'])
def restart_bot():
    """Перезапускает бота"""
    try:
        # Сначала останавливаем бота
        stop_response = stop_bot()
        if isinstance(stop_response, tuple) and stop_response[1] == 500:
            # Если остановка не удалась, возвращаем ошибку
            return stop_response
            
        # Ждем немного, чтобы убедиться, что все процессы завершены
        time.sleep(2)
        
        # Затем запускаем бота снова
        start_response = start_bot()
        if isinstance(start_response, tuple) and start_response[1] == 500:
            # Если запуск не удался, возвращаем ошибку
            return start_response
            
        return jsonify({'success': True, 'message': 'Бот перезапущен'})
    except Exception as e:
        logging.error(f"Ошибка при перезапуске бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Запускаем сервер Flask в режиме отладки (НЕ использовать в продакшн)
    app.run(debug=True, host='0.0.0.0', port=5000)
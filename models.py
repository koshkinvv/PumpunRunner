"""
Модели базы данных для приложения.
"""
from app import db
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime

# Эта функция больше не используется, оставлена для совместимости с существующим кодом
def create_tables():
    """
    ВНИМАНИЕ: Эта функция устарела и оставлена только для обратной совместимости.
    Вместо нее следует использовать db.create_all() с контекстом приложения Flask.
    """
    import logging
    logging.warning("Функция create_tables() устарела, используйте db.create_all() в контексте приложения Flask")
    return False

# Функция для форматирования даты
def format_date(date_obj):
    """Форматирует объект даты в строку."""
    if date_obj is None:
        return "Не указано"
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
        except ValueError:
            return date_obj
    try:
        return date_obj.strftime("%d.%m.%Y")
    except Exception:
        return str(date_obj)

class User(db.Model):
    """Таблица пользователей."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User {self.id}: {self.telegram_id} ({self.username})>"


class RunnerProfile(db.Model):
    """Таблица профилей бегунов."""
    __tablename__ = 'runner_profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    distance = Column(Float)  # Дистанция забега
    competition_date = Column(DateTime)  # Дата соревнования
    gender = Column(String(10))  # Пол
    age = Column(Integer)  # Возраст
    height = Column(Float)  # Рост
    weight = Column(Float)  # Вес
    experience = Column(String(50))  # Опыт бега
    goal = Column(String(255))  # Цель тренировок
    target_time = Column(String(20))  # Целевое время
    fitness_level = Column(String(50))  # Уровень физической подготовки
    comfortable_pace = Column(String(20))  # Комфортный пэйс для бега с разговором
    weekly_volume = Column(Float, default=0)  # Еженедельный объем бега (км)
    training_start_date = Column(DateTime)  # Дата начала тренировок
    training_days_per_week = Column(Integer)  # Кол-во тренировочных дней в неделю
    preferred_training_days = Column(String(255))  # Предпочитаемые дни для тренировок
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<RunnerProfile {self.id}: User {self.user_id}, Distance {self.distance}km>"


class PaymentStatus(db.Model):
    """Таблица статуса оплаты."""
    __tablename__ = 'payment_statuses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    payment_agreed = Column(Boolean, default=False)
    subscription_end_date = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PaymentStatus {self.id}: User {self.user_id}, Agreed: {self.payment_agreed}>"


class TrainingPlan(db.Model):
    """Таблица планов тренировок."""
    __tablename__ = 'training_plans'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    plan_data = Column(Text)  # JSON-данные плана
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<TrainingPlan {self.id}: User {self.user_id}>"


class TrainingCompletion(db.Model):
    """Таблица выполненных тренировок."""
    __tablename__ = 'training_completions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    training_id = Column(String(100), nullable=False)  # ID тренировки в плане
    completed_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<TrainingCompletion {self.id}: User {self.user_id}, Training {self.training_id}>"


class TrainingCancellation(db.Model):
    """Таблица отмененных тренировок."""
    __tablename__ = 'training_cancellations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    training_id = Column(String(100), nullable=False)  # ID тренировки в плане
    cancelled_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<TrainingCancellation {self.id}: User {self.user_id}, Training {self.training_id}>"

class BotMetrics(db.Model):
    """Таблица метрик работы бота."""
    __tablename__ = 'bot_metrics'
    
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, nullable=False, default=func.now())
    end_time = Column(DateTime)
    uptime_seconds = Column(Integer)
    processed_messages = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<BotMetrics {self.id}: Start {self.start_time}>"
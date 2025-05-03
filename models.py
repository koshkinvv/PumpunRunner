import psycopg2
import psycopg2.extras
import json
from datetime import datetime
from config import DB_CONFIG, logging

def create_tables():
    """Create the necessary tables in the database if they don't exist."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Drop runner_profiles table if exists (для исправления ошибки с типом данных)
        try:
            cursor.execute("DROP TABLE IF EXISTS runner_profiles CASCADE")
            logging.info("Existing runner_profiles table dropped for schema update")
        except Exception as e:
            logging.error(f"Error dropping runner_profiles table: {e}")
            conn.rollback()
        
        # Create runner_profiles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runner_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            distance FLOAT,
            competition_date VARCHAR(255),
            gender VARCHAR(10),
            age INTEGER,
            height FLOAT,
            weight FLOAT,
            experience VARCHAR(255),
            goal VARCHAR(50),
            target_time VARCHAR(50),
            fitness_level VARCHAR(50),
            weekly_volume FLOAT,
            training_start_date VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create training_plans table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_plans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            plan_name VARCHAR(255),
            plan_description TEXT,
            plan_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create completed_trainings table for tracking training completion status
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS completed_trainings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            plan_id INTEGER REFERENCES training_plans(id) ON DELETE CASCADE,
            training_day INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'completed',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        logging.info("Tables created successfully")
    except Exception as e:
        logging.error(f"Error creating database tables: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def format_date(date_str):
    """Convert date string to a database-friendly format."""
    # Проверка на специальный случай "Нет конкретной даты" или "Нет"
    if date_str == "Нет конкретной даты" or date_str == "Нет":
        return date_str
        
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        # If parsing fails, return the original string
        return date_str

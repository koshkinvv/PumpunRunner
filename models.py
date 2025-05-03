import psycopg2
import psycopg2.extras
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
        
        # Create runner_profiles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runner_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            distance FLOAT,
            competition_date DATE,
            gender VARCHAR(10),
            age INTEGER,
            height FLOAT,
            weight FLOAT,
            experience VARCHAR(255),
            goal VARCHAR(50),
            target_time VARCHAR(50),
            fitness_level VARCHAR(50),
            weekly_volume FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        # If parsing fails, return the original string
        return date_str

import psycopg2
import psycopg2.extras
from datetime import datetime
from config import DB_CONFIG, logging
from models import format_date

class DBManager:
    """Database manager for PostgreSQL operations."""
    
    @staticmethod
    def get_connection():
        """Establish a database connection."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except Exception as e:
            logging.error(f"Database connection error: {e}")
            return None
    
    @staticmethod
    def add_user(telegram_id, username=None, first_name=None, last_name=None):
        """
        Add a new user to the database or retrieve existing user.
        
        Args:
            telegram_id: User's Telegram ID
            username: User's Telegram username
            first_name: User's first name
            last_name: User's last name
            
        Returns:
            User ID if successful, None otherwise
        """
        conn = None
        try:
            conn = DBManager.get_connection()
            with conn.cursor() as cursor:
                # Check if user already exists
                cursor.execute(
                    "SELECT id FROM users WHERE telegram_id = %s",
                    (telegram_id,)
                )
                user = cursor.fetchone()
                
                if user:
                    # Update existing user
                    cursor.execute(
                        """
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s 
                        WHERE telegram_id = %s
                        RETURNING id
                        """,
                        (username, first_name, last_name, telegram_id)
                    )
                else:
                    # Insert new user
                    cursor.execute(
                        """
                        INSERT INTO users (telegram_id, username, first_name, last_name)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (telegram_id, username, first_name, last_name)
                    )
                
                user_id = cursor.fetchone()[0]
                conn.commit()
                return user_id
                
        except Exception as e:
            logging.error(f"Error adding/updating user: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def save_runner_profile(user_id, profile_data):
        """
        Save a runner's profile to the database.
        
        Args:
            user_id: Database user ID
            profile_data: Dictionary containing runner profile information
            
        Returns:
            True if successful, False otherwise
        """
        conn = None
        try:
            conn = DBManager.get_connection()
            with conn.cursor() as cursor:
                # Check if profile already exists
                cursor.execute(
                    "SELECT id FROM runner_profiles WHERE user_id = %s",
                    (user_id,)
                )
                profile = cursor.fetchone()
                
                # Format the competition date
                if "competition_date" in profile_data:
                    profile_data["competition_date"] = format_date(profile_data["competition_date"])
                
                if profile:
                    # Update existing profile
                    query = """
                    UPDATE runner_profiles SET 
                        distance = %(distance)s,
                        competition_date = %(competition_date)s,
                        gender = %(gender)s,
                        age = %(age)s,
                        height = %(height)s,
                        weight = %(weight)s,
                        experience = %(experience)s,
                        goal = %(goal)s,
                        target_time = %(target_time)s,
                        fitness_level = %(fitness_level)s,
                        weekly_volume = %(weekly_volume)s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %(user_id)s
                    """
                    cursor.execute(query, {**profile_data, "user_id": user_id})
                else:
                    # Insert new profile
                    query = """
                    INSERT INTO runner_profiles (
                        user_id, distance, competition_date, gender, age, 
                        height, weight, experience, goal, target_time, 
                        fitness_level, weekly_volume
                    ) VALUES (
                        %(user_id)s, %(distance)s, %(competition_date)s, %(gender)s, %(age)s,
                        %(height)s, %(weight)s, %(experience)s, %(goal)s, %(target_time)s,
                        %(fitness_level)s, %(weekly_volume)s
                    )
                    """
                    cursor.execute(query, {**profile_data, "user_id": user_id})
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error saving runner profile: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_user_id(telegram_id):
        """
        Get database user ID from Telegram ID.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            User ID if found, None otherwise
        """
        conn = None
        try:
            conn = DBManager.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE telegram_id = %s",
                    (telegram_id,)
                )
                user = cursor.fetchone()
                return user[0] if user else None
                
        except Exception as e:
            logging.error(f"Error getting user ID: {e}")
            return None
        finally:
            if conn:
                conn.close()

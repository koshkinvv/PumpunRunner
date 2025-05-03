import psycopg2
import psycopg2.extras
import json
from config import DB_CONFIG, logging

class TrainingPlanManager:
    """Manager for training plan operations."""
    
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
    def save_training_plan(user_id, plan_data):
        """
        Save a training plan to the database.
        
        Args:
            user_id: Database user ID
            plan_data: Dictionary containing the training plan
            
        Returns:
            Plan ID if successful, None otherwise
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor() as cursor:
                # Insert training plan
                query = """
                INSERT INTO training_plans (
                    user_id, plan_name, plan_description, plan_data
                ) VALUES (
                    %(user_id)s, %(plan_name)s, %(plan_description)s, %(plan_data)s
                )
                RETURNING id
                """
                
                cursor.execute(query, {
                    "user_id": user_id,
                    "plan_name": plan_data.get("plan_name", "Беговой план"),
                    "plan_description": plan_data.get("plan_description", ""),
                    "plan_data": json.dumps(plan_data)
                })
                
                plan_id = cursor.fetchone()[0]
                conn.commit()
                return plan_id
                
        except Exception as e:
            logging.error(f"Error saving training plan: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_latest_training_plan(user_id):
        """
        Get the latest training plan for a user.
        
        Args:
            user_id: Database user ID
            
        Returns:
            Dictionary containing the training plan if found, None otherwise
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query latest plan
                cursor.execute(
                    """
                    SELECT id, plan_name, plan_description, plan_data, created_at 
                    FROM training_plans 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 1
                    """,
                    (user_id,)
                )
                
                plan = cursor.fetchone()
                if plan:
                    result = dict(plan)
                    # Parse JSON data
                    result["plan_data"] = json.loads(result["plan_data"])
                    return result
                return None
                
        except Exception as e:
            logging.error(f"Error getting training plan: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_all_training_plans(user_id):
        """
        Get all training plans for a user.
        
        Args:
            user_id: Database user ID
            
        Returns:
            List of dictionaries containing the training plans
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query all plans
                cursor.execute(
                    """
                    SELECT id, plan_name, plan_description, plan_data, created_at 
                    FROM training_plans 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                    """,
                    (user_id,)
                )
                
                plans = cursor.fetchall()
                results = []
                for plan in plans:
                    plan_dict = dict(plan)
                    # Parse JSON data
                    plan_dict["plan_data"] = json.loads(plan_dict["plan_data"])
                    results.append(plan_dict)
                return results
                
        except Exception as e:
            logging.error(f"Error getting training plans: {e}")
            return []
        finally:
            if conn:
                conn.close()
                
    @staticmethod
    def mark_training_completed(user_id, plan_id, training_day):
        """
        Mark a training day as completed.
        
        Args:
            user_id: Database user ID
            plan_id: Training plan ID
            training_day: Day number in the training plan (1-based)
            
        Returns:
            True if successful, False otherwise
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor() as cursor:
                # Check if this training day is already marked
                cursor.execute(
                    """
                    SELECT id FROM completed_trainings 
                    WHERE user_id = %s AND plan_id = %s AND training_day = %s
                    """,
                    (user_id, plan_id, training_day)
                )
                
                existing = cursor.fetchone()
                
                if existing:
                    # Already marked, update timestamp
                    cursor.execute(
                        """
                        UPDATE completed_trainings 
                        SET completed_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                        """,
                        (existing[0],)
                    )
                else:
                    # New completion
                    cursor.execute(
                        """
                        INSERT INTO completed_trainings (
                            user_id, plan_id, training_day
                        ) VALUES (
                            %s, %s, %s
                        )
                        """,
                        (user_id, plan_id, training_day)
                    )
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error marking training as completed: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_completed_trainings(user_id, plan_id):
        """
        Get a list of completed training days for a plan.
        
        Args:
            user_id: Database user ID
            plan_id: Training plan ID
            
        Returns:
            List of completed training day numbers
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT training_day 
                    FROM completed_trainings 
                    WHERE user_id = %s AND plan_id = %s
                    ORDER BY training_day
                    """,
                    (user_id, plan_id)
                )
                
                results = cursor.fetchall()
                return [row[0] for row in results]
                
        except Exception as e:
            logging.error(f"Error getting completed trainings: {e}")
            return []
        finally:
            if conn:
                conn.close()
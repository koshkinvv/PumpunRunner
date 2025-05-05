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
    def update_training_plan(user_id, plan_id, plan_data):
        """
        Update an existing training plan in the database.
        
        Args:
            user_id: Database user ID
            plan_id: ID of the plan to update
            plan_data: Dictionary containing the updated training plan
            
        Returns:
            True if successful, False otherwise
        """
        try:
            connection = TrainingPlanManager.get_connection()
            cursor = connection.cursor()
            
            # Convert plan data to JSON string
            plan_json = json.dumps(plan_data, ensure_ascii=False)
            
            # Update the plan
            # First check if the updated_at column exists
            try:
                check_query = """
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'training_plans' AND column_name = 'updated_at'
                """
                cursor.execute(check_query)
                has_updated_at = cursor.fetchone() is not None

                if has_updated_at:
                    query = """
                        UPDATE training_plans
                        SET plan_data = %s, updated_at = NOW()
                        WHERE id = %s AND user_id = %s
                        RETURNING id
                    """
                else:
                    # Для обратной совместимости, если колонка еще не создана
                    query = """
                        UPDATE training_plans
                        SET plan_data = %s
                        WHERE id = %s AND user_id = %s
                        RETURNING id
                    """
                    logging.warning("Column updated_at does not exist in training_plans table. Using backward compatible query.")
            except Exception as e:
                logging.error(f"Error checking for updated_at column: {e}")
                query = """
                    UPDATE training_plans
                    SET plan_data = %s
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                """
            cursor.execute(query, (plan_json, plan_id, user_id))
            result = cursor.fetchone()
            
            # Commit the changes
            connection.commit()
            
            return result is not None
        except Exception as e:
            logging.error(f"Error updating training plan: {e}")
            return False
        finally:
            if connection:
                connection.close()
                
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
    def get_training_plan(user_id, plan_id):
        """
        Get a specific training plan by ID.
        
        Args:
            user_id: Database user ID
            plan_id: ID of the plan to retrieve
            
        Returns:
            Dictionary containing the training plan if found, None otherwise
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query plan by ID
                cursor.execute(
                    """
                    SELECT id, plan_name, plan_description, plan_data, created_at 
                    FROM training_plans 
                    WHERE user_id = %s AND id = %s
                    """,
                    (user_id, plan_id)
                )
                
                plan = cursor.fetchone()
                if plan:
                    result = dict(plan)
                    # Parse JSON data only if it's still a string
                    if isinstance(result["plan_data"], str):
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
                    # Parse JSON data only if it's still a string
                    if isinstance(result["plan_data"], str):
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
                    # Parse JSON data only if it's still a string
                    if isinstance(plan_dict["plan_data"], str):
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
                    # Already marked, update status and timestamp
                    cursor.execute(
                        """
                        UPDATE completed_trainings 
                        SET status = 'completed', updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                        """,
                        (existing[0],)
                    )
                else:
                    # New completion
                    cursor.execute(
                        """
                        INSERT INTO completed_trainings (
                            user_id, plan_id, training_day, status
                        ) VALUES (
                            %s, %s, %s, 'completed'
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
    def mark_training_canceled(user_id, plan_id, training_day):
        """
        Mark a training day as canceled.
        
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
                    # Already marked, update status and timestamp
                    cursor.execute(
                        """
                        UPDATE completed_trainings 
                        SET status = 'canceled', updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                        """,
                        (existing[0],)
                    )
                else:
                    # New cancellation
                    cursor.execute(
                        """
                        INSERT INTO completed_trainings (
                            user_id, plan_id, training_day, status
                        ) VALUES (
                            %s, %s, %s, 'canceled'
                        )
                        """,
                        (user_id, plan_id, training_day)
                    )
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error marking training as canceled: {e}")
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
                    WHERE user_id = %s AND plan_id = %s AND status = 'completed'
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
                
    @staticmethod
    def get_canceled_trainings(user_id, plan_id):
        """
        Get a list of canceled training days for a plan.
        
        Args:
            user_id: Database user ID
            plan_id: Training plan ID
            
        Returns:
            List of canceled training day numbers
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT training_day 
                    FROM completed_trainings 
                    WHERE user_id = %s AND plan_id = %s AND status = 'canceled'
                    ORDER BY training_day
                    """,
                    (user_id, plan_id)
                )
                
                results = cursor.fetchall()
                return [row[0] for row in results]
                
        except Exception as e:
            logging.error(f"Error getting canceled trainings: {e}")
            return []
        finally:
            if conn:
                conn.close()
                
    @staticmethod
    def get_all_processed_trainings(user_id, plan_id):
        """
        Get a list of all processed (completed or canceled) training days for a plan.
        
        Args:
            user_id: Database user ID
            plan_id: Training plan ID
            
        Returns:
            List of processed training day numbers
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
            logging.error(f"Error getting processed trainings: {e}")
            return []
        finally:
            if conn:
                conn.close()
                
    @staticmethod
    def calculate_total_completed_distance(user_id, plan_id):
        """
        Calculate the total distance of completed trainings for a specific plan.
        
        Args:
            user_id: Database user ID
            plan_id: Training plan ID
            
        Returns:
            Total distance in kilometers (float)
        """
        conn = None
        try:
            conn = TrainingPlanManager.get_connection()
            with conn.cursor() as cursor:
                # Get the plan data
                cursor.execute(
                    """
                    SELECT plan_data 
                    FROM training_plans 
                    WHERE id = %s AND user_id = %s
                    """,
                    (plan_id, user_id)
                )
                
                plan_data_row = cursor.fetchone()
                if not plan_data_row:
                    return 0
                
                plan_data = plan_data_row[0]
                if isinstance(plan_data, str):
                    plan_data = json.loads(plan_data)
                
                # Get completed trainings
                cursor.execute(
                    """
                    SELECT training_day 
                    FROM completed_trainings 
                    WHERE user_id = %s AND plan_id = %s AND status = 'completed'
                    ORDER BY training_day
                    """,
                    (user_id, plan_id)
                )
                
                completed_days = [row[0] for row in cursor.fetchall()]
                if not completed_days:
                    return 0
                
                # Calculate total distance
                total_distance = 0
                logging.info(f"Расчет дистанции для плана {plan_id}. Завершенные дни: {completed_days}")
                
                for day_num in completed_days:
                    day_idx = day_num - 1
                    if day_idx < 0 or day_idx >= len(plan_data.get('training_days', [])):
                        logging.warning(f"Индекс дня {day_idx} за пределами тренировочных дней")
                        continue
                    
                    day_data = plan_data['training_days'][day_idx]
                    distance_raw = day_data.get('distance', '0 км')
                    logging.info(f"Дистанция для дня {day_num}: '{distance_raw}'")
                    
                    try:
                        # Разбиваем строку и берем первое значение (число) перед единицами измерения
                        distance_str = distance_raw.split()[0].replace(',', '.')
                        distance = float(distance_str)
                        total_distance += distance
                        logging.info(f"  Добавлено {distance} км")
                    except (ValueError, TypeError, IndexError) as e:
                        # Skip if distance cannot be parsed as float
                        logging.warning(f"  Не удалось распарсить дистанцию '{distance_raw}': {e}")
                        continue
                
                logging.info(f"Итоговая дистанция для плана {plan_id}: {total_distance} км")
                return total_distance
                
        except Exception as e:
            logging.error(f"Error calculating total distance: {e}")
            return 0
        finally:
            if conn:
                conn.close()
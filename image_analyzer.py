import os
import base64
import io
from datetime import datetime, timedelta
from openai import OpenAI
from config import logging

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

class ImageAnalyzer:
    """Service for analyzing fitness tracker screenshots with OpenAI API."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)
    
    def analyze_workout_screenshot(self, image_data):
        """
        Analyze a fitness tracker screenshot to extract workout details.
        
        Args:
            image_data: Image data in bytes
            
        Returns:
            Dictionary containing workout details (date, distance, time, pace, etc.)
        """
        try:
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": 
                     "Ты эксперт по анализу скриншотов фитнес-трекеров. "
                     "Твоя задача - извлечь всю доступную информацию о тренировке из скриншота. "
                     "Дай ответ ТОЛЬКО в формате JSON со следующими полями (если информация доступна): "
                     "дата (в формате ДД.ММ.ГГГГ), "
                     "время тренировки (если указано, в формате ЧЧ:ММ), "
                     "дистанция_км (в километрах, только число), "
                     "длительность (в формате ММ:СС или ЧЧ:ММ:СС), "
                     "темп (в формате ММ:СС/км), "
                     "калории, "
                     "набор_высоты, "
                     "тип_тренировки (например, бег, ходьба и т.д.), "
                     "название_приложения (Nike Run, Strava, Garmin и т.д.). "
                     "Обязательно укажи хотя бы дату и дистанцию_км, если они видны на скриншоте."
                    },
                    {"role": "user", "content": [
                        {
                            "type": "text", 
                            "text": "Проанализируй этот скриншот фитнес-трекера и извлеки информацию о тренировке."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]}
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            
            # Get the response content
            result = response.choices[0].message.content
            logging.info(f"OpenAI анализ изображения: {result}")
            
            import json
            workout_data = json.loads(result)
            
            # Convert date format if available (ДД.ММ.ГГГГ -> YYYY-MM-DD)
            if "дата" in workout_data:
                try:
                    date_obj = datetime.strptime(workout_data["дата"], "%d.%m.%Y")
                    workout_data["formatted_date"] = date_obj.strftime("%Y-%m-%d")
                except Exception as e:
                    logging.warning(f"Error converting date format: {e}")
                    try:
                        # Try alternative formats (e.g., "April 17, 2025")
                        months = {
                            "January": "01", "February": "02", "March": "03", "April": "04",
                            "May": "05", "June": "06", "July": "07", "August": "08",
                            "September": "09", "October": "10", "November": "11", "December": "12",
                            "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
                            "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
                            "Nov": "11", "Dec": "12"
                        }
                        
                        if "April" in workout_data["дата"] and "2025" in workout_data["дата"]:
                            # Special case for "April 17, 2025" format
                            parts = workout_data["дата"].replace(",", "").split()
                            month = months.get(parts[0], "01")
                            day = parts[1].zfill(2)
                            year = parts[2]
                            workout_data["formatted_date"] = f"{year}-{month}-{day}"
                            workout_data["дата"] = f"{day}.{month}.{year}"
                    except Exception as inner_e:
                        logging.warning(f"Alternative date format conversion failed: {inner_e}")
            
            return workout_data
            
        except Exception as e:
            logging.error(f"Error analyzing workout screenshot: {e}")
            return {"error": str(e)}
    
    def find_matching_training(self, training_days, workout_data):
        """
        Find a matching training day based on workout data.
        
        Args:
            training_days: List of training day dictionaries
            workout_data: Workout data extracted from screenshot
            
        Returns:
            Tuple of (matching_day_index, matching_score) or (None, 0) if no match
        """
        if not workout_data or not training_days:
            logging.warning("Пустые данные тренировки или план тренировок отсутствует")
            return None, 0
        
        logging.info(f"Поиск совпадающей тренировки. Данные из скриншота: {workout_data}")
        
        best_match = None
        best_score = 0
        
        # Get the workout date
        workout_date = None
        if "formatted_date" in workout_data:
            workout_date = workout_data["formatted_date"]
            logging.info(f"Дата тренировки из скриншота: {workout_date}")
        
        # Get workout distance
        workout_distance = None
        if "дистанция_км" in workout_data:
            try:
                workout_distance = float(workout_data["дистанция_км"])
                logging.info(f"Дистанция тренировки из скриншота: {workout_distance} км")
            except ValueError:
                logging.warning(f"Could not convert distance to float: {workout_data['дистанция_км']}")
        
        # Log all training days for debugging
        for i, day in enumerate(training_days):
            training_type = day.get('training_type', day.get('type', 'Не указан'))
            logging.info(f"План, день {i+1}: {day.get('day', 'Не указан')} ({day.get('date', 'Нет даты')}), тип: {training_type}, дистанция: {day.get('distance', 'Не указана')}")
        
        # Loop through training days to find matches
        for i, day in enumerate(training_days):
            score = 0
            day_log = f"День {i+1}: {day.get('day', 'Неизвестно')} ({day.get('date', 'Неизвестно')})"
            
            # Extract date from training plan
            training_date = None
            if "date" in day:
                try:
                    # Convert from "ДД.ММ.ГГГГ" to "YYYY-MM-DD"
                    date_parts = day["date"].split(".")
                    if len(date_parts) == 3:
                        training_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
                        day_log += f", дата: {training_date}"
                except Exception as e:
                    logging.warning(f"Error parsing training date: {e}")
            
            # Extract distance from training plan
            training_distance = None
            if "distance" in day:
                try:
                    # Extract numeric value from distance string (e.g., "5 км" -> 5)
                    import re
                    distance_match = re.search(r'(\d+(\.\d+)?)', day["distance"])
                    if distance_match:
                        training_distance = float(distance_match.group(1))
                        day_log += f", дистанция: {training_distance} км"
                except Exception as e:
                    logging.warning(f"Error parsing training distance: {e}")
            
            # Compare dates (highest priority)
            date_score = 0
            if workout_date and training_date and workout_date == training_date:
                date_score = 10  # High score for exact date match
                day_log += f", точное совпадение даты (+10)"
            elif workout_date and training_date:
                # Check if dates are close (within 1 day)
                try:
                    workout_date_obj = datetime.strptime(workout_date, "%Y-%m-%d")
                    training_date_obj = datetime.strptime(training_date, "%Y-%m-%d")
                    days_diff = abs((workout_date_obj - training_date_obj).days)
                    if days_diff <= 1:
                        date_score = 5  # Medium score for close dates
                        day_log += f", близкая дата (разница {days_diff} дней) (+5)"
                except Exception as e:
                    logging.warning(f"Error comparing dates: {e}")
            score += date_score
            
            # Compare distances (second priority)
            distance_score = 0
            if workout_distance and training_distance:
                # Calculate distance difference percentage
                diff_percent = abs(workout_distance - training_distance) / max(workout_distance, training_distance) * 100
                day_log += f", разница дистанций: {diff_percent:.1f}%"
                
                if diff_percent <= 10:  # Within 10%
                    distance_score = 3  # High score for similar distance
                    day_log += " (+3)"
                elif diff_percent <= 20:  # Within 20%
                    distance_score = 2  # Medium score for somewhat similar distance
                    day_log += " (+2)"
                elif diff_percent <= 30:  # Within 30%
                    distance_score = 1  # Low score for different but close distance
                    day_log += " (+1)"
            score += distance_score
            
            # Compare type (lowest priority)
            type_score = 0
            workout_type = workout_data.get("тип_тренировки", "").lower()
            training_type = day.get("training_type", "").lower()
            if not training_type:
                training_type = day.get("type", "").lower()
            
            if workout_type and training_type:
                day_log += f", типы: '{workout_type}' vs '{training_type}'"
                if workout_type in training_type or training_type in workout_type:
                    type_score = 1  # Small bonus for matching type
                    day_log += " (+1)"
            score += type_score
            
            # Log the score for this training day
            day_log += f" = Итого баллов: {score}"
            logging.info(day_log)
            
            # Update best match if current score is higher
            if score > best_score:
                best_score = score
                best_match = i
                logging.info(f"Новый лучший результат: День {i+1} с {score} баллами")
        
        # Return the best match (index and score)
        if best_match is not None:
            logging.info(f"Лучшее совпадение: День {best_match+1} с {best_score} баллами")
        else:
            logging.info("Не найдено подходящих совпадений")
        
        return best_match, best_score
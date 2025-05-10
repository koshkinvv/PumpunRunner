import os
import json
import logging
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

class OpenAIService:
    """Service for interacting with OpenAI API."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)
    
    def generate_training_plan(self, runner_profile):
        """
        Generate a personalized running training plan based on runner profile.
        
        Args:
            runner_profile: Dictionary containing runner profile information
            
        Returns:
            Dictionary containing training plan for 7 days
        """
        try:
            logging.info(f"Начинаем генерацию плана тренировок для пользователя с профилем: {runner_profile}")
            
            # Prepare prompt with runner profile information
            prompt = self._create_prompt(runner_profile)
            logging.info(f"Создан промпт для OpenAI: {prompt[:100]}...")
            
            # Получаем даты для тренировок, учитывая выбранную пользователем дату начала
            from datetime import datetime, timedelta
            import pytz
            
            # Используем Московское время (UTC+3)
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Проверяем, указал ли пользователь дату начала тренировок
            user_start_date = runner_profile.get('training_start_date_text', runner_profile.get('training_start_date', None))
            
            # Попытка распарсить дату начала тренировок
            start_date = None
            
            if user_start_date and user_start_date.lower() != 'сегодня' and user_start_date.lower() != 'не знаю':
                try:
                    # Попробуем распарсить дату в формате "ДД.ММ.ГГГГ"
                    logging.info(f"Пытаемся распарсить дату начала тренировок: {user_start_date}")
                    
                    # Обрабатываем несколько возможных форматов
                    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m"]
                    
                    for fmt in formats:
                        try:
                            if fmt == "%d.%m":
                                # Для формата без года добавляем текущий год
                                current_year = datetime.now().year
                                date_with_year = f"{user_start_date}.{current_year}"
                                start_date = datetime.strptime(date_with_year, "%d.%m.%Y")
                            else:
                                start_date = datetime.strptime(user_start_date, fmt)
                            
                            start_date = moscow_tz.localize(start_date)
                            logging.info(f"Успешно распарсили дату: {start_date.strftime('%d.%m.%Y')}")
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logging.error(f"Ошибка при парсинге даты начала тренировок: {e}")
            
            # Если не удалось распарсить дату или она не была указана, используем текущую дату
            if not start_date:
                start_date = datetime.now(pytz.UTC).astimezone(moscow_tz)
                logging.info(f"Используем текущую дату: {start_date.strftime('%d.%m.%Y')}")
            
            logging.info(f"Дата начала тренировок: {start_date.strftime('%d.%m.%Y %H:%M:%S')}")
            
            # Получаем предпочитаемые дни тренировок
            preferred_days_str = runner_profile.get('preferred_training_days', '')
            preferred_days = []
            
            if preferred_days_str:
                # Словарь для преобразования сокращений дней недели в числа (0 - понедельник, 6 - воскресенье)
                day_name_to_number = {
                    'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6,
                    'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3, 
                    'пятница': 4, 'суббота': 5, 'воскресенье': 6
                }
                
                # Разбиваем строку предпочитаемых дней и преобразуем в числа
                for day in preferred_days_str.lower().split(','):
                    day = day.strip()
                    if day in day_name_to_number:
                        preferred_days.append(day_name_to_number[day])
            
            logging.info(f"Предпочитаемые дни недели: {preferred_days}")
            
            # Если предпочитаемые дни не указаны, используем все дни недели
            if not preferred_days:
                preferred_days = list(range(7))  # 0 - понедельник, 6 - воскресенье
            
            # Количество тренировочных дней в неделю (по умолчанию 3)
            training_days_count = int(runner_profile.get('training_days_per_week', 3))
            
            # Убедимся, что у нас достаточно дней для тренировок
            if len(preferred_days) < training_days_count:
                logging.warning(f"Недостаточно предпочитаемых дней ({len(preferred_days)}) для требуемого количества тренировок ({training_days_count}). Добавляем дополнительные дни.")
                for i in range(7):
                    if i not in preferred_days:
                        preferred_days.append(i)
                        if len(preferred_days) >= training_days_count:
                            break
            
            # Если указано больше предпочитаемых дней, чем нужно для тренировок, используем первые N дней
            if len(preferred_days) > training_days_count:
                preferred_days = preferred_days[:training_days_count]
            
            # Сортируем дни недели, чтобы они шли по порядку
            preferred_days.sort()
            
            logging.info(f"Отсортированные предпочитаемые дни недели: {preferred_days}")
            
            # Определяем ближайшие даты для тренировок с учетом предпочитаемых дней недели
            training_dates = []
            current_date = start_date
            
            # Проверяем, если стартовая дата раньше текущей даты, используем текущую
            now = datetime.now(pytz.UTC).astimezone(moscow_tz)
            if current_date.date() < now.date():
                current_date = now
                logging.warning(f"Стартовая дата в прошлом, используем текущую: {current_date.strftime('%d.%m.%Y')}")
            
            # Получаем день недели для стартовой даты (0 - понедельник, 6 - воскресенье)
            start_weekday = current_date.weekday()
            logging.info(f"День недели стартовой даты: {start_weekday} ({current_date.strftime('%A')})")
            
            # Находим первый подходящий день для начала тренировок
            days_to_add = 0
            if preferred_days:
                # Ищем ближайший предпочитаемый день недели, начиная со стартовой даты
                min_days_to_add = float('inf')
                for day in preferred_days:
                    # Вычисляем, сколько дней нужно добавить к стартовой дате
                    if day >= start_weekday:
                        days = day - start_weekday
                    else:
                        days = 7 - start_weekday + day
                    
                    if days < min_days_to_add:
                        min_days_to_add = days
                
                days_to_add = min_days_to_add
            
            # Добавляем дни к стартовой дате, чтобы получить первый день тренировки
            first_training_date = current_date + timedelta(days=days_to_add)
            logging.info(f"Первый день тренировки: {first_training_date.strftime('%d.%m.%Y (%A)')}")
            
            # Генерируем даты для всех тренировочных дней
            training_day_counter = 0
            date_to_check = first_training_date
            
            while training_day_counter < training_days_count:
                weekday = date_to_check.weekday()
                
                if weekday in preferred_days:
                    training_dates.append(date_to_check)
                    training_day_counter += 1
                    logging.info(f"Добавлена дата тренировки: {date_to_check.strftime('%d.%m.%Y (%A)')}")
                
                date_to_check = date_to_check + timedelta(days=1)
            
            # Преобразуем даты в строки формата "ДД.ММ.YYYY" для использования в плане
            dates = [date.strftime("%d.%m.%Y") for date in training_dates]
            
            # Для промпта OpenAI используем первый день тренировки
            first_day_str = dates[0]
            # Если есть второй день тренировки, используем его, иначе используем день после первого
            second_day_str = dates[1] if len(dates) > 1 else (training_dates[0] + timedelta(days=1)).strftime("%d.%m.%Y")
            
            logging.info(f"Сгенерированные даты для плана: {dates}")
            logging.info(f"Первый день: {first_day_str}, второй день: {second_day_str}")
            
            # Преобразуем числовые дни недели в названия для промпта
            day_number_to_name = {
                0: "Понедельник (Пн)", 
                1: "Вторник (Вт)", 
                2: "Среда (Ср)", 
                3: "Четверг (Чт)", 
                4: "Пятница (Пт)", 
                5: "Суббота (Сб)", 
                6: "Воскресенье (Вс)"
            }
            
            preferred_days_names = [day_number_to_name[day] for day in preferred_days]
            preferred_days_text = ", ".join(preferred_days_names)
            
            # Получаем словарь дат тренировок с днями недели
            training_dates_with_weekdays = {}
            for date in training_dates:
                weekday_num = date.weekday()
                weekday_name = day_number_to_name[weekday_num]
                date_str = date.strftime("%d.%m.%Y")
                training_dates_with_weekdays[date_str] = weekday_name
            
            # Форматируем информацию о датах тренировок для промпта
            training_dates_info = "\n".join([f"- {date}: {weekday}" for date, weekday in training_dates_with_weekdays.items()])
            
            # Call OpenAI API
            logging.info("Отправляем запрос к OpenAI API")
            try:
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": 
                         f"Ты опытный беговой тренер. Твоя задача - создать персонализированный план "
                         f"тренировок для бегуна, используя ТОЛЬКО указанные даты в точном соответствии с предпочтениями пользователя.\n\n"
                         f"Пользователь выбрал следующие предпочитаемые дни недели для тренировок: {preferred_days_text}.\n"
                         f"На основе этого выбора и указанной даты начала тренировок, были определены следующие даты тренировок:\n{training_dates_info}\n\n"
                         f"ВАЖНО: План тренировок должен включать ТОЛЬКО ЭТИ ДАТЫ и ДНИ НЕДЕЛИ. "
                         f"НЕ ДОБАВЛЯЙ дополнительные дни тренировок кроме указанных выше дат.\n\n"
                         f"План должен быть структурирован строго по этим дням недели с указанными датами.\n\n"
                         f"Каждый день в плане должен обязательно содержать: день недели (например, 'Вторник'), "
                         f"дату в формате ДД.ММ.YYYY (например, '07.05.2025'), тип тренировки, дистанцию, целевой темп "
                         f"и детальное описание тренировки.\n\n"
                         f"План должен включать все важные компоненты тренировочного процесса: длительные пробежки, интервальные тренировки, "
                         f"темповые тренировки и восстановительные пробежки, в зависимости от цели и уровня подготовки бегуна.\n\n"
                         f"Учитывай цель бегуна, его физическую подготовку и еженедельный объем.\n\n"
                         f"Отвечай только в указанном JSON формате на русском языке."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                logging.info("Получен ответ от OpenAI API")
            except Exception as api_error:
                logging.error(f"Ошибка при вызове OpenAI API: {api_error}")
                raise
            
            # Parse and return the response
            try:
                response_content = response.choices[0].message.content
                logging.info(f"Получен ответ от OpenAI (первые 100 символов): {response_content[:100]}...")
                
                # Проверяем, что ответ имеет правильный формат JSON
                if not response_content.strip().startswith('{') or not response_content.strip().endswith('}'):
                    logging.error(f"Ответ от OpenAI не имеет правильный формат JSON: {response_content}")
                    # Попробуем найти JSON в ответе, если он существует
                    import re
                    json_match = re.search(r'({.*})', response_content, re.DOTALL)
                    if json_match:
                        response_content = json_match.group(1)
                        logging.info(f"Извлечен JSON из ответа: {response_content[:100]}...")
                    else:
                        logging.error("Не удалось извлечь JSON из ответа")
                        # Создаем базовый план в качестве резервного варианта
                        return {
                            "plan_name": "Базовый беговой план",
                            "plan_description": "План создан автоматически из-за ошибки в генерации",
                            "plan_data": {
                                "training_days": [
                                    {
                                        "day": "Понедельник",
                                        "date": "10.05.2025",
                                        "training_type": "Легкая пробежка",
                                        "distance": "5 км",
                                        "pace": "6:00-6:30 мин/км",
                                        "description": "Легкая восстановительная пробежка в комфортном темпе."
                                    },
                                    {
                                        "day": "Среда",
                                        "date": "12.05.2025",
                                        "training_type": "Темповая тренировка",
                                        "distance": "7 км",
                                        "pace": "5:30-6:00 мин/км",
                                        "description": "Разминка 2 км, темповая часть 3 км, заминка 2 км."
                                    },
                                    {
                                        "day": "Суббота",
                                        "date": "15.05.2025",
                                        "training_type": "Длительная пробежка",
                                        "distance": "10 км",
                                        "pace": "6:00-6:30 мин/км",
                                        "description": "Длительная пробежка в аэробном темпе для развития выносливости."
                                    }
                                ]
                            }
                        }
                
                # Парсим JSON
                plan_json = json.loads(response_content)
                logging.info(f"JSON успешно распарсен: {str(plan_json)[:200]}...")
                
                # Проверяем наличие необходимых полей
                if "plan_name" not in plan_json:
                    logging.warning("В ответе OpenAI отсутствует plan_name, добавляем значение по умолчанию")
                    plan_json["plan_name"] = "Персонализированный беговой план"
                
                if "plan_description" not in plan_json:
                    logging.warning("В ответе OpenAI отсутствует plan_description, добавляем значение по умолчанию")
                    plan_json["plan_description"] = "План тренировок, сгенерированный с учетом вашего профиля"
                
                # Проверяем структуру plan_data/training_days
                if "plan_data" not in plan_json and "training_days" in plan_json:
                    logging.info("Преобразуем старую структуру в новую (перемещаем training_days в plan_data)")
                    plan_json["plan_data"] = {"training_days": plan_json["training_days"]}
                    del plan_json["training_days"]
                elif "training_days" in plan_json and "plan_data" not in plan_json:
                    logging.info("Автоматически создаем структуру plan_data на основе training_days")
                    plan_json["plan_data"] = {"training_days": plan_json["training_days"]}
                elif "plan_data" not in plan_json:
                    logging.error("В ответе OpenAI нет ни plan_data, ни training_days")
                    plan_json["plan_data"] = {
                        "training_days": [
                            {
                                "day": "Понедельник",
                                "date": "10.05.2025",
                                "training_type": "Легкая пробежка",
                                "distance": "5 км",
                                "pace": "6:00-6:30 мин/км",
                                "description": "Легкая восстановительная пробежка в комфортном темпе."
                            },
                            {
                                "day": "Среда", 
                                "date": "12.05.2025",
                                "training_type": "Темповая тренировка",
                                "distance": "7 км",
                                "pace": "5:30-6:00 мин/км",
                                "description": "Разминка 2 км, темповая часть 3 км, заминка 2 км."
                            },
                            {
                                "day": "Суббота",
                                "date": "15.05.2025",
                                "training_type": "Длительная пробежка", 
                                "distance": "10 км",
                                "pace": "6:00-6:30 мин/км",
                                "description": "Длительная пробежка в аэробном темпе для развития выносливости."
                            }
                        ]
                    }
                
                return plan_json
                
            except Exception as json_error:
                logging.error(f"Ошибка при обработке ответа от OpenAI: {json_error}")
                logging.error(f"Полученный ответ: {response.choices[0].message.content}")
                
                # Создаем резервный план в случае ошибки
                logging.info("Создаем резервный план из-за ошибки обработки")
                return {
                    "plan_name": "Базовый беговой план",
                    "plan_description": "План создан автоматически из-за ошибки в генерации",
                    "plan_data": {
                        "training_days": [
                            {
                                "day": "Понедельник",
                                "date": "10.05.2025",
                                "training_type": "Легкая пробежка",
                                "distance": "5 км",
                                "pace": "6:00-6:30 мин/км",
                                "description": "Легкая восстановительная пробежка в комфортном темпе."
                            },
                            {
                                "day": "Среда",
                                "date": "12.05.2025",
                                "training_type": "Темповая тренировка",
                                "distance": "7 км",
                                "pace": "5:30-6:00 мин/км",
                                "description": "Разминка 2 км, темповая часть 3 км, заминка 2 км."
                            },
                            {
                                "day": "Суббота",
                                "date": "15.05.2025",
                                "training_type": "Длительная пробежка",
                                "distance": "10 км",
                                "pace": "6:00-6:30 мин/км",
                                "description": "Длительная пробежка в аэробном темпе для развития выносливости."
                            }
                        ]
                    }
                }
            
        except Exception as e:
            logging.error(f"Error generating training plan: {e}")
            raise
    
    def _create_prompt(self, profile):
        """
        Create a prompt for OpenAI API based on runner profile.
        
        Args:
            profile: Dictionary containing runner profile information
            
        Returns:
            String prompt
        """
        # Determine the start date for training
        start_date = profile.get('training_start_date_text', profile.get('training_start_date', 'Сегодня'))
        
        # Construct a detailed prompt based on runner profile
        prompt = (
            f"Создай персонализированный план беговых тренировок на 7 дней для бегуна со следующим профилем:\n\n"
            f"- Целевая дистанция: {profile.get('distance', 'Неизвестно')} км\n"
            f"- Дата соревнования: {profile.get('competition_date', 'Неизвестно')}\n"
            f"- Дата начала тренировок: {start_date}\n"
            f"- Пол: {profile.get('gender', 'Неизвестно')}\n"
            f"- Возраст: {profile.get('age', 'Неизвестно')}\n"
            f"- Рост: {profile.get('height', 'Неизвестно')} см\n"
            f"- Вес: {profile.get('weight', 'Неизвестно')} кг\n"
            f"- Цель: {profile.get('goal', 'Неизвестно')}\n"
            f"- Предпочитаемое количество тренировок в неделю: {profile.get('training_days_per_week', '3')}\n"
            f"- Предпочитаемые дни тренировок: {profile.get('preferred_training_days', 'Не указано')}\n"
        )
        
        if profile.get('goal') == 'Улучшить время':
            prompt += f"- Целевое время: {profile.get('target_time', 'Неизвестно')}\n"
            
        prompt += (
            f"- Уровень физической подготовки: {profile.get('fitness_level', 'Неизвестно')}\n"
            f"- Комфортный темп бега: {profile.get('comfortable_pace', 'Неизвестно')}\n"
            f"- Еженедельный объем бега: {profile.get('weekly_volume_text', profile.get('weekly_volume', 'Неизвестно'))} км\n\n"
            "План должен включать разнообразные тренировки (длительные, темповые, интервальные, восстановительные) "
            "с учетом уровня подготовки бегуна.\n\n"
            "Для каждого дня недели укажи:\n"
            "1. День недели\n"
            "2. Тип тренировки\n"
            "3. Дистанцию\n"
            "4. Целевой темп\n"
            "5. Детальное описание тренировки\n\n"
            "Ответ предоставь в следующем JSON формате:\n"
            "{\n"
            '  "plan_name": "Название плана (включающее цель бегуна)",\n'
            '  "plan_description": "Общее описание плана",\n'
            '  "training_days": [\n'
            '    {\n'
            '      "day": "День недели (например, Понедельник)",\n'
            '      "date": "Дата в формате ДД.ММ.ГГГГ",\n'
            '      "training_type": "Тип тренировки",\n'
            '      "distance": "Дистанция в км",\n'
            '      "pace": "Целевой темп",\n'
            '      "description": "Подробное описание тренировки"\n'
            '    },\n'
            '    ...\n'
            '  ]\n'
            "}"
        )
        
        return prompt
        
    def adjust_training_plan(self, runner_profile, current_plan, completed_day_num, planned_distance, actual_distance):
        """
        Adjust the current training plan based on the significant difference between
        planned and actual distances.
        
        Args:
            runner_profile: Dictionary containing runner profile information
            current_plan: Dictionary containing the current training plan
            completed_day_num: The day number (1-based index) that was just completed
            planned_distance: The planned distance for the completed training
            actual_distance: The actual distance that was run
            
        Returns:
            Dictionary containing the adjusted training plan
        """
        try:
            # Calculate the difference percentage
            if planned_distance > 0:
                diff_percent = abs(actual_distance - planned_distance) / planned_distance * 100
            else:
                diff_percent = 0
                
            # Prepare prompt for plan adjustment
            prompt = (
                f"Ты тренер по бегу. Необходимо скорректировать план тренировок по бегу, "
                f"так как фактическое выполнение отличается от запланированного.\n\n"
                
                f"Профиль бегуна:\n"
                f"- Дистанция соревнования: {runner_profile.get('distance', 'Не указано')} км\n"
                f"- Дата соревнования: {runner_profile.get('competition_date', 'Не указано')}\n"
                f"- Пол: {runner_profile.get('gender', 'Не указано')}\n"
                f"- Возраст: {runner_profile.get('age', 'Не указано')}\n"
                f"- Рост: {runner_profile.get('height', 'Не указано')} см\n"
                f"- Вес: {runner_profile.get('weight', 'Не указано')} кг\n"
                f"- Опыт бега: {runner_profile.get('experience', 'Не указано')}\n"
                f"- Цель: {runner_profile.get('goal', 'Не указано')}\n"
                f"- Целевое время: {runner_profile.get('target_time', 'Не указано')}\n"
                f"- Уровень физической подготовки: {runner_profile.get('fitness', 'Не указано')}\n"
                f"- Комфортный темп бега: {runner_profile.get('comfortable_pace', 'Не указано')}\n"
                f"- Еженедельный объем бега: {runner_profile.get('weekly_volume', 'Не указано')} км\n\n"
                
                f"Текущий план тренировок:\n{json.dumps(current_plan, ensure_ascii=False, indent=2)}\n\n"
                
                f"День {completed_day_num} только что был выполнен.\n"
                f"Запланированная дистанция: {planned_distance} км\n"
                f"Фактическая дистанция: {actual_distance} км\n"
                f"Разница: {diff_percent:.1f}%\n\n"
                
                f"Пожалуйста, скорректируй оставшиеся дни плана, учитывая фактическое выполнение. "
                f"Не меняй дни, которые уже прошли (дни до {completed_day_num} включительно).\n\n"
                
                f"Ответ предоставь в формате JSON, сохраняя структуру оригинального плана."
            )
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Ты опытный тренер по бегу, который составляет персонализированные планы тренировок."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            # Parse response
            adjusted_plan = json.loads(response.choices[0].message.content)
            
            return adjusted_plan
        except Exception as e:
            logging.error(f"Error adjusting training plan: {e}")
            return None
    
    def generate_training_plan_continuation(self, runner_profile, completed_distances, current_plan):
        """
        Generate a continuation of an existing running training plan based on runner profile
        and completed trainings.
        
        Args:
            runner_profile: Dictionary containing runner profile information
            completed_distances: Total distance in km completed in previous plan
            current_plan: Dictionary containing the current training plan
            
        Returns:
            Dictionary containing a new training plan for 7 days
        """
        try:
            logging.info("Starting generate_training_plan_continuation")
            logging.info(f"Runner profile ID: {runner_profile.get('id', 'Unknown')}")
            logging.info(f"Completed distances: {completed_distances} km")
            logging.info(f"Current plan: {current_plan.get('id', 'Unknown')}")
            
            # Проверяем, как быстро пользователь выполнил предыдущий план
            from datetime import datetime, timedelta
            
            # Пытаемся получить информацию о сроках выполнения предыдущего плана
            rapid_completion = False
            days_passed = 7  # По умолчанию считаем, что план выполнялся неделю
            try:
                logging.info("Checking plan completion timing")
                if current_plan and 'id' in current_plan:
                    # Получаем время создания плана
                    plan_creation_time = current_plan.get('created_at')
                    logging.info(f"Plan creation time (raw): {plan_creation_time}")
                    
                    if plan_creation_time:
                        # Преобразуем строку времени в объект datetime
                        if isinstance(plan_creation_time, str):
                            try:
                                plan_creation_time = datetime.strptime(plan_creation_time, "%Y-%m-%d %H:%M:%S")
                                logging.info(f"Parsed plan creation time: {plan_creation_time}")
                            except ValueError as e:
                                logging.error(f"Error parsing creation time: {e}")
                                plan_creation_time = datetime.now() - timedelta(days=7)  # Fallback
                        
                        # Текущее время с учетом часового пояса Москвы
                        import pytz
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        current_time = datetime.now(pytz.UTC).astimezone(moscow_tz)
                        logging.info(f"Current time: {current_time}")
                        
                        # Рассчитываем разницу во времени
                        # Если plan_creation_time не имеет информации о часовом поясе, делаем его наивным
                        if plan_creation_time.tzinfo is not None:
                            plan_creation_time = plan_creation_time.replace(tzinfo=None)
                        current_time_naive = current_time.replace(tzinfo=None)
                        
                        time_difference = current_time_naive - plan_creation_time
                        days_passed = time_difference.days
                        logging.info(f"Days passed since plan creation: {days_passed}")
                        
                        # Если план был выполнен менее чем за 3 дня, считаем это быстрым выполнением
                        if days_passed < 3:
                            rapid_completion = True
                            logging.info("Rapid completion detected!")
                else:
                    logging.warning("Current plan doesn't have ID or is None")
            except Exception as e:
                logging.warning(f"Error checking plan completion timing: {e}")
            
            # Создаем основную информацию о профиле
            profile_info = f"""Создай продолжение плана беговых тренировок на 7 дней для бегуна со следующим профилем:

- Целевая дистанция: {runner_profile.get('distance', 'Неизвестно')} км
- Дата соревнования: {runner_profile.get('competition_date', 'Неизвестно')}
- Пол: {runner_profile.get('gender', 'Неизвестно')}
- Возраст: {runner_profile.get('age', 'Неизвестно')}
- Рост: {runner_profile.get('height', 'Неизвестно')} см
- Вес: {runner_profile.get('weight', 'Неизвестно')} кг
- Цель: {runner_profile.get('goal', 'Неизвестно')}
- Предпочитаемое количество тренировок в неделю: {runner_profile.get('training_days_per_week', '3')}
- Предпочитаемые дни тренировок: {runner_profile.get('preferred_training_days', 'Не указано')}
"""
            
            # Добавляем целевое время, если цель - улучшить время
            if runner_profile.get('goal') == 'Улучшить время':
                profile_info += f"- Целевое время: {runner_profile.get('target_time', 'Неизвестно')}\n"
                
            # Добавляем уровень физической подготовки, комфортный темп и недельный объем
            profile_info += f"""- Уровень физической подготовки: {runner_profile.get('fitness_level', 'Неизвестно')}
- Комфортный темп бега: {runner_profile.get('comfortable_pace', 'Неизвестно')}
- Еженедельный объем бега: {runner_profile.get('weekly_volume', 'Неизвестно')} км

- Бегун успешно выполнил предыдущий план тренировок за {days_passed} дней и пробежал в общей сложности {completed_distances:.1f} км.

ВАЖНО: Этот план является ПРОДОЛЖЕНИЕМ предыдущего! Учитывай рост физической подготовки и повышение выносливости бегуна. Увеличь нагрузку и интенсивность тренировок по сравнению с предыдущим планом.
"""
            
            # Если пользователь выполнил план очень быстро, делаем план еще более интенсивным
            if rapid_completion:
                profile_info += f"""
ОЧЕНЬ ВАЖНО: Бегун выполнил предыдущий план чрезвычайно быстро (всего за {days_passed} дней)!
Это однозначно указывает на то, что его физическая форма значительно лучше ожидаемой.
Необходимо значительно увеличить интенсивность и сложность нового плана:

1. Увеличь километраж каждой тренировки минимум на 30-40%
2. Существенно увеличь интенсивность и целевой темп всех тренировок
3. Добавь не менее 2-3 сложных интервальных тренировок для развития скоростных качеств и выносливости
4. Включи в план более длинные и сложные тренировки для развития выносливости
5. Повысь сложность всех упражнений, учитывая высокий уровень готовности бегуна
"""
            
            # Добавляем сводку по предыдущему плану
            profile_info += """
Предыдущий план включал следующие типы тренировок:
"""
            
            # Создаем сводку по типам тренировок
            training_types = {}
            for day in current_plan.get('training_days', []):
                training_type = day.get('training_type', '')
                if training_type in training_types:
                    training_types[training_type] += 1
                else:
                    training_types[training_type] = 1
            
            # Формируем строку со сводкой
            training_summary = ""
            for training_type, count in training_types.items():
                training_summary += f"- {training_type}: {count} раз\n"
            
            # Инструкции для нового плана
            instructions = """
План должен включать разнообразные тренировки (длительные, темповые, интервальные, восстановительные) с учетом возросшего уровня подготовки бегуна.

Для каждого дня недели укажи:
1. День недели
2. Тип тренировки
3. Дистанцию
4. Целевой темп
5. Детальное описание тренировки

Ответ предоставь в следующем JSON формате:
{
  "plan_name": "Название плана (включающее 'Продолжение тренировок')",
  "plan_description": "Общее описание плана",
  "training_days": [
    {
      "day": "День недели (например, Понедельник)",
      "date": "Дата в формате ДД.ММ.ГГГГ",
      "training_type": "Тип тренировки",
      "distance": "Дистанция в км",
      "pace": "Целевой темп",
      "description": "Подробное описание тренировки"
    }
  ]
}
"""
            
            # Объединяем все части подсказки
            prompt = profile_info + training_summary + instructions
            
            # Получаем даты для тренировок
            import pytz
            
            # Используем Московское время (UTC+3)
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Проверяем, указал ли пользователь дату начала тренировок в профиле
            user_start_date = runner_profile.get('training_start_date_text', runner_profile.get('training_start_date', None))
            
            # Попытка распарсить дату начала тренировок
            start_date = None
            
            if user_start_date and user_start_date.lower() != 'сегодня' and user_start_date.lower() != 'не знаю':
                try:
                    # Попробуем распарсить дату в формате "ДД.ММ.ГГГГ"
                    logging.info(f"Продолжение плана - пытаемся распарсить дату начала: {user_start_date}")
                    
                    # Обрабатываем несколько возможных форматов
                    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m"]
                    
                    for fmt in formats:
                        try:
                            if fmt == "%d.%m":
                                # Для формата без года добавляем текущий год
                                current_year = datetime.now().year
                                date_with_year = f"{user_start_date}.{current_year}"
                                start_date = datetime.strptime(date_with_year, "%d.%m.%Y")
                            else:
                                start_date = datetime.strptime(user_start_date, fmt)
                            
                            start_date = moscow_tz.localize(start_date)
                            logging.info(f"Успешно распарсили дату продолжения: {start_date.strftime('%d.%m.%Y')}")
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logging.error(f"Ошибка при парсинге даты начала продолжения: {e}")
            
            # Если не удалось распарсить дату или она не была указана, используем текущую дату
            if not start_date:
                start_date = datetime.now(pytz.UTC).astimezone(moscow_tz)
                logging.info(f"Используем текущую дату для продолжения: {start_date.strftime('%d.%m.%Y')}")
            
            logging.info(f"Дата начала продолжения плана: {start_date.strftime('%d.%m.%Y %H:%M:%S')}")
            
            # Получаем предпочитаемые дни тренировок
            preferred_days_str = runner_profile.get('preferred_training_days', '')
            preferred_days = []
            
            if preferred_days_str:
                # Словарь для преобразования сокращений дней недели в числа (0 - понедельник, 6 - воскресенье)
                day_name_to_number = {
                    'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6,
                    'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3, 
                    'пятница': 4, 'суббота': 5, 'воскресенье': 6
                }
                
                # Разбиваем строку предпочитаемых дней и преобразуем в числа
                for day in preferred_days_str.lower().split(','):
                    day = day.strip()
                    if day in day_name_to_number:
                        preferred_days.append(day_name_to_number[day])
            
            logging.info(f"Предпочитаемые дни недели для продолжения: {preferred_days}")
            
            # Если предпочитаемые дни не указаны, используем все дни недели
            if not preferred_days:
                preferred_days = list(range(7))  # 0 - понедельник, 6 - воскресенье
            
            # Количество тренировочных дней в неделю (по умолчанию 3)
            training_days_count = int(runner_profile.get('training_days_per_week', 3))
            
            # Убедимся, что у нас достаточно дней для тренировок
            if len(preferred_days) < training_days_count:
                logging.warning(f"Недостаточно предпочитаемых дней ({len(preferred_days)}) для требуемого количества тренировок ({training_days_count}). Добавляем дополнительные дни.")
                for i in range(7):
                    if i not in preferred_days:
                        preferred_days.append(i)
                        if len(preferred_days) >= training_days_count:
                            break
            
            # Если указано больше предпочитаемых дней, чем нужно для тренировок, используем все указанные дни
            # НЕ сокращаем список, потому что это продолжение плана
            
            # Сортируем дни недели, чтобы они шли по порядку
            preferred_days.sort()
            
            logging.info(f"Отсортированные предпочитаемые дни недели для продолжения: {preferred_days}")
            
            # Определяем ближайшие даты для тренировок с учетом предпочитаемых дней недели
            training_dates = []
            current_date = start_date
            
            # Проверяем, если стартовая дата раньше текущей даты, используем текущую
            now = datetime.now(pytz.UTC).astimezone(moscow_tz)
            if current_date.date() < now.date():
                current_date = now
                logging.warning(f"Стартовая дата в прошлом, используем текущую: {current_date.strftime('%d.%m.%Y')}")
            
            # Получаем день недели для стартовой даты (0 - понедельник, 6 - воскресенье)
            start_weekday = current_date.weekday()
            logging.info(f"День недели стартовой даты продолжения: {start_weekday} ({current_date.strftime('%A')})")
            
            # Находим первый подходящий день для начала тренировок
            days_to_add = 0
            if preferred_days:
                # Ищем ближайший предпочитаемый день недели, начиная со стартовой даты
                min_days_to_add = float('inf')
                for day in preferred_days:
                    # Вычисляем, сколько дней нужно добавить к стартовой дате
                    if day >= start_weekday:
                        days = day - start_weekday
                    else:
                        days = 7 - start_weekday + day
                    
                    if days < min_days_to_add:
                        min_days_to_add = days
                
                days_to_add = min_days_to_add
            
            # Добавляем дни к стартовой дате, чтобы получить первый день тренировки
            first_training_date = current_date + timedelta(days=days_to_add)
            logging.info(f"Первый день продолжения тренировки: {first_training_date.strftime('%d.%m.%Y (%A)')}")
            
            # Генерируем даты для всех тренировочных дней
            training_day_counter = 0
            date_to_check = first_training_date
            
            while training_day_counter < training_days_count:
                weekday = date_to_check.weekday()
                
                if weekday in preferred_days:
                    training_dates.append(date_to_check)
                    training_day_counter += 1
                    logging.info(f"Добавлена дата продолжения тренировки: {date_to_check.strftime('%d.%m.%Y (%A)')}")
                
                date_to_check = date_to_check + timedelta(days=1)
            
            # Преобразуем даты в строки формата "ДД.ММ.YYYY" для использования в плане
            dates = [date.strftime("%d.%m.%Y") for date in training_dates]
            
            # Преобразуем числовые дни недели в названия для промпта
            day_number_to_name = {
                0: "Понедельник (Пн)", 
                1: "Вторник (Вт)", 
                2: "Среда (Ср)", 
                3: "Четверг (Чт)", 
                4: "Пятница (Пт)", 
                5: "Суббота (Сб)", 
                6: "Воскресенье (Вс)"
            }
            
            preferred_days_names = [day_number_to_name[day] for day in preferred_days]
            preferred_days_text = ", ".join(preferred_days_names)
            
            # Получаем словарь дат тренировок с днями недели
            training_dates_with_weekdays = {}
            for date in training_dates:
                weekday_num = date.weekday()
                weekday_name = day_number_to_name[weekday_num]
                date_str = date.strftime("%d.%m.%Y")
                training_dates_with_weekdays[date_str] = weekday_name
            
            # Форматируем информацию о датах тренировок для промпта
            training_dates_info = "\n".join([f"- {date}: {weekday}" for date, weekday in training_dates_with_weekdays.items()])
            
            # Для промпта OpenAI используем первый день тренировки
            first_day_str = dates[0] if dates else start_date.strftime("%d.%m.%Y")
            # Если есть второй день тренировки, используем его, иначе используем день после первого
            second_day_str = dates[1] if len(dates) > 1 else (training_dates[0] + timedelta(days=1)).strftime("%d.%m.%Y") if training_dates else (start_date + timedelta(days=1)).strftime("%d.%m.%Y")
            
            logging.info(f"Сгенерированные даты для продолжения плана: {dates}")
            logging.info(f"Первый день: {first_day_str}, второй день: {second_day_str}")
            
            # Вызываем API OpenAI
            logging.info("Calling OpenAI API for plan continuation")
            try:
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": 
                         f"Ты опытный беговой тренер. Твоя задача - создать продолжение персонализированного плана "
                         f"тренировок для бегуна, используя ТОЛЬКО указанные даты в точном соответствии с предпочтениями пользователя.\n\n"
                         f"Пользователь выбрал следующие предпочитаемые дни недели для тренировок: {preferred_days_text}.\n"
                         f"На основе этого выбора и указанной даты начала тренировок, были определены следующие даты тренировок:\n{training_dates_info}\n\n"
                         f"ВАЖНО: План тренировок должен включать ТОЛЬКО ЭТИ ДАТЫ и ДНИ НЕДЕЛИ. "
                         f"НЕ ДОБАВЛЯЙ дополнительные дни тренировок кроме указанных выше дат.\n\n"
                         f"План должен быть структурирован строго по этим дням недели с указанными датами.\n\n"
                         f"Каждый день в плане должен обязательно содержать: день недели (например, 'Вторник'), "
                         f"дату в формате ДД.ММ.YYYY (например, '07.05.2025'), тип тренировки, дистанцию, целевой темп "
                         f"и детальное описание тренировки.\n\n"
                         f"Учитывай, что бегун стал сильнее после завершения предыдущего плана, поэтому новый план должен "
                         f"быть более интенсивным, с увеличенным километражем и сложностью.\n\n"
                         f"Отвечай только в указанном JSON формате на русском языке."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                logging.info("OpenAI API response received successfully")
            except Exception as e:
                logging.error(f"Error calling OpenAI API: {e}")
                raise
            
            # Разбираем и возвращаем ответ
            plan_json = json.loads(response.choices[0].message.content)
            return plan_json
            
        except Exception as e:
            logging.error(f"Error generating training plan continuation: {e}")
            raise
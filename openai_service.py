import os
import json
from openai import OpenAI
from config import logging

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
            # Prepare prompt with runner profile information
            prompt = self._create_prompt(runner_profile)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": 
                     "Ты опытный беговой тренер. Твоя задача - создать персонализированный план "
                     "тренировок на 7 дней, основываясь на профиле бегуна. "
                     "План должен начинаться с указанной даты (или с сегодняшнего дня, если дата не указана) "
                     "и быть структурирован по дням недели с конкретными датами. План должен включать детальное "
                     "описание каждой тренировки (дистанция, темп, тип тренировки). "
                     "Учитывай цель бегуна, его физическую подготовку и еженедельный объем. "
                     "Отвечай только в указанном JSON формате на русском языке."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            # Parse and return the response
            plan_json = json.loads(response.choices[0].message.content)
            return plan_json
            
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
        )
        
        if profile.get('goal') == 'Улучшить время':
            prompt += f"- Целевое время: {profile.get('target_time', 'Неизвестно')}\n"
            
        prompt += (
            f"- Уровень физической подготовки: {profile.get('fitness_level', 'Неизвестно')}\n"
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
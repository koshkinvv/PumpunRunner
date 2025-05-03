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
            # Create basic profile information
            profile_info = f"""Создай продолжение плана беговых тренировок на 7 дней для бегуна со следующим профилем:

- Целевая дистанция: {runner_profile.get('distance', 'Неизвестно')} км
- Дата соревнования: {runner_profile.get('competition_date', 'Неизвестно')}
- Пол: {runner_profile.get('gender', 'Неизвестно')}
- Возраст: {runner_profile.get('age', 'Неизвестно')}
- Рост: {runner_profile.get('height', 'Неизвестно')} см
- Вес: {runner_profile.get('weight', 'Неизвестно')} кг
- Цель: {runner_profile.get('goal', 'Неизвестно')}
"""
            
            # Add target time if goal is to improve time
            if runner_profile.get('goal') == 'Улучшить время':
                profile_info += f"- Целевое время: {runner_profile.get('target_time', 'Неизвестно')}\n"
                
            # Add fitness level and weekly volume
            profile_info += f"""- Уровень физической подготовки: {runner_profile.get('fitness_level', 'Неизвестно')}
- Еженедельный объем бега: {runner_profile.get('weekly_volume', 'Неизвестно')}

- Бегун успешно выполнил предыдущий план тренировок и пробежал в общей сложности {completed_distances:.1f} км.

ВАЖНО: Этот план является ПРОДОЛЖЕНИЕМ предыдущего! Учитывай рост физической подготовки и повышение выносливости бегуна. Увеличь нагрузку и интенсивность тренировок по сравнению с предыдущим планом.

Предыдущий план включал следующие типы тренировок:
"""
            
            # Add summary of previous plan
            training_types = {}
            for day in current_plan.get('training_days', []):
                training_type = day.get('training_type', '')
                if training_type in training_types:
                    training_types[training_type] += 1
                else:
                    training_types[training_type] = 1
            
            training_summary = ""
            for training_type, count in training_types.items():
                training_summary += f"- {training_type}: {count} раз\n"
            
            # Instructions for the new plan
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
    },
    ...
  ]
}
"""
            
            # Combine all parts of the prompt
            prompt = profile_info + training_summary + instructions
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": 
                     "Ты опытный беговой тренер. Твоя задача - создать продолжение персонализированного плана "
                     "тренировок на 7 дней, основываясь на профиле бегуна и на результатах предыдущих тренировок. "
                     "План должен начинаться с сегодняшнего дня и быть структурирован по дням недели с конкретными датами. "
                     "План должен включать детальное описание каждой тренировки (дистанция, темп, тип тренировки). "
                     "Учитывай, что бегун стал сильнее после завершения предыдущего плана, поэтому новый план должен "
                     "быть более интенсивным, с увеличенным километражем и сложностью. "
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
            logging.error(f"Error generating training plan continuation: {e}")
            raise
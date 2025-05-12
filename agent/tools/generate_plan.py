#!/usr/bin/env python3
"""
MCP-инструмент для генерации тренировочных планов на основе профиля бегуна.
Совместим с OpenAI Agents SDK и может использоваться как самостоятельно, так и 
в составе агента.

Используется методология из книг:
- "Training Distance Runners" (Jack Daniels)
- "Science of Running" (Steve Magness)
- "Periodization Training for Sports" (Tudor Bompa)
"""

import os
import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"


class RecentRun(BaseModel):
    """Модель для представления недавних пробежек"""
    date: str
    distance: float
    pace: str


class RunnerProfile(BaseModel):
    """Модель для представления профиля бегуна"""
    age: int
    gender: str
    weight: float
    height: float
    level: str  # beginner / amateur / advanced
    weekly_distance: float
    goal_distance: str
    goal_date: str
    available_days: List[str]
    recent_runs: Optional[List[RecentRun]] = []


class GeneratePlanUseCase:
    """
    MCP-инструмент для генерации тренировочных планов.
    Соответствует требованиям Model Context Protocol для использования
    в OpenAI Agents SDK.
    """
    id = "generate_training_plan"
    description = "Генерация 7-дневного бегового плана на основе профиля пользователя"
    input_model = RunnerProfile
    output_model = str

    def __init__(self):
        """Инициализация инструмента с OpenAI клиентом"""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        self.client = OpenAI(api_key=api_key)

    def __call__(self, input: RunnerProfile) -> str:
        """
        Генерирует тренировочный план на основе профиля бегуна.
        
        Args:
            input: Профиль бегуна в формате RunnerProfile
            
        Returns:
            str: Сгенерированный план тренировок в markdown-формате
        """
        # Формируем системный и пользовательский промпты
        system_prompt = self._create_system_prompt()
        user_prompt = self._create_user_prompt(input)
        
        # Вызываем OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            # Получаем и обрабатываем результат
            content = response.choices[0].message.content
            plan_data = json.loads(content)
            
            # Форматируем план в markdown
            formatted_plan = self._format_training_plan(plan_data)
            return formatted_plan
            
        except Exception as e:
            return f"Произошла ошибка при создании плана: {str(e)}"

    def _create_system_prompt(self) -> str:
        """
        Создает системный промпт на основе методологий из книг
        Jack Daniels, Steve Magness, Tudor Bompa.
        
        Returns:
            str: Системный промпт для OpenAI
        """
        return """Ты опытный тренер по бегу, эксперт с глубокими знаниями передовых методик тренировок, 
основанных на лучших книгах и исследованиях:

• Jack Daniels ("Training Distance Runners") - разработал формулы расчета VDOT и нагрузки, определил оптимальные пульсовые зоны
• Steve Magness ("Science of Running") - исследовал физиологию бега и психологию подготовки на научной основе
• Tudor Bompa ("Periodization Training for Sports") - создал принципы периодизации тренировок для достижения пика формы к соревнованиям
• Brad Stulberg & Steve Magness ("Peak Performance") - разработали методики достижения пиковых состояний с учетом восстановления
• David Joyce & Daniel Lewindon ("High-Performance Training for Sports") - систематизировали современные методы спортивной подготовки

При составлении тренировочных планов ты:

1) Тщательно анализируешь профиль бегуна:
   - Физические параметры (пол, возраст, вес, рост) для корректировки нагрузок
   - Текущий уровень подготовки и опыт для выбора подходящих тренировок
   - Целевую дистанцию и дату соревнования для расчета периодизации
   - Комфортный темп и недельный объем для оценки текущего уровня
   - Недавние пробежки для понимания текущей формы

2) Создаешь научно-обоснованные планы, включая:
   - Прогрессивное увеличение нагрузки с соблюдением принципа суперкомпенсации
   - Чередование типов тренировок разной интенсивности (80:20 правило)
   - Разнообразие тренировок: длительные аэробные, темповые, интервальные, восстановительные
   - Адаптацию тренировок к уровню бегуна с допустимым темпом прогресса 5-10% в неделю
   - Использование формул Джека Дэниелса для расчета оптимальных зон интенсивности

3) Даешь практические рекомендации по:
   - Темпам бега для каждого типа тренировок (с учетом физиологических зон)
   - Технике выполнения упражнений и профилактике травм
   - Восстановлению между тренировками, включая сон и питание
   - Корректировке плана при отклонениях от графика
   - Ментальной подготовке к соревнованиям

Твоя задача - создать персонализированный план, который поможет бегуну достичь цели безопасно и эффективно, с учетом научных принципов и практического опыта тренерской работы."""

    def _create_user_prompt(self, profile: RunnerProfile) -> str:
        """
        Создает пользовательский промпт на основе профиля бегуна.
        
        Args:
            profile: Профиль бегуна
            
        Returns:
            str: Пользовательский промпт для OpenAI
        """
        # Преобразуем уровень подготовки в русскоязычный формат
        level_map = {
            "beginner": "Начинающий",
            "amateur": "Любитель",
            "advanced": "Продвинутый"
        }
        level_ru = level_map.get(profile.level, profile.level)
        
        # Форматируем недавние пробежки, если они есть
        recent_runs_text = ""
        if profile.recent_runs:
            recent_runs_text = "Недавние пробежки:\n"
            for run in profile.recent_runs:
                recent_runs_text += f"- {run.date}: {run.distance} км, темп {run.pace} мин/км\n"
        
        # Форматируем дни недели, доступные для тренировок
        available_days_text = ", ".join(profile.available_days)
        
        # Создаем промпт
        prompt = f"""Составь персонализированный план беговых тренировок на 7 дней для бегуна со следующим профилем:

Пол: {profile.gender}
Возраст: {profile.age}
Рост: {profile.height} см
Вес: {profile.weight} кг
Уровень подготовки: {level_ru}
Еженедельный объем бега: {profile.weekly_distance} км
Целевая дистанция: {profile.goal_distance}
Дата соревнования: {profile.goal_date}
Доступные дни для тренировок: {available_days_text}
{recent_runs_text}

План должен включать:
1. Конкретные дни недели с учетом доступных дней
2. Дистанцию и целевой темп для каждой тренировки
3. Оптимальный пульсовой диапазон 
4. Детальное описание выполнения с тактикой
5. Общий недельный объем и его распределение

Ответ должен быть в формате JSON со следующими полями:
- "plan_name": название плана
- "plan_description": описание цели и особенностей плана
- "weekly_volume": общий объем за неделю в км (число)
- "intensity_distribution": распределение интенсивности в процентах
- "training_days": массив объектов с тренировками, включающий:
  * "day": номер дня (1-7)
  * "day_of_week": день недели на русском
  * "date": дата в формате ГГГГ-ММ-ДД
  * "workout_type": тип тренировки
  * "distance": дистанция в км (число)
  * "pace": рекомендуемый темп в мин/км
  * "heart_rate": диапазон пульса
  * "description": подробное описание тренировки
  * "purpose": цель этой тренировки
- "rest_days": массив объектов с днями отдыха, включающий:
  * "day": номер дня (1-7)
  * "day_of_week": день недели на русском
  * "date": дата в формате ГГГГ-ММ-ДД
  * "activity": рекомендуемая активность в день отдыха
  * "purpose": цель отдыха
- "recommendations": объект с рекомендациями:
  * "nutrition": питание
  * "recovery": восстановление
  * "progression": развитие в последующие недели
  * "adjustments": рекомендации по корректировке плана

Используй методики из книг Jack Daniels "Training Distance Runners", Steve Magness "Science of Running" и Tudor Bompa "Periodization Training for Sports" для определения оптимальных зон интенсивности и нагрузки."""
        
        return prompt

    def _format_training_plan(self, plan: dict) -> str:
        """
        Форматирует план тренировок в markdown формат.
        
        Args:
            plan: Словарь с данными плана
            
        Returns:
            str: Форматированный план в markdown
        """
        output = []
        output.append(f"# 🏃 {plan.get('plan_name', 'Персонализированный план тренировок')}")
        output.append("")
        
        # Описание плана
        output.append(f"## 📝 Описание")
        output.append(plan.get('plan_description', 'Нет описания'))
        output.append("")
        
        # Общая статистика
        output.append(f"## 📊 Общая информация")
        output.append(f"- **Общий объем**: {plan.get('weekly_volume', '?')} км")
        output.append(f"- **Распределение интенсивности**: {plan.get('intensity_distribution', '?')}")
        output.append("")
        
        # Тренировочные дни
        output.append("## 🏃‍♂️ Тренировочные дни")
        for day in plan.get('training_days', []):
            output.append(f"### День {day.get('day', '?')} - {day.get('day_of_week', '?')} ({day.get('date', '?')})")
            output.append(f"**Тип**: {day.get('workout_type', 'Не указан')}")
            output.append(f"**Дистанция**: {day.get('distance', '?')} км")
            output.append(f"**Темп**: {day.get('pace', 'Не указан')}")
            output.append(f"**Пульс**: {day.get('heart_rate', 'Не указан')}")
            output.append("")
            output.append("**Описание**:")
            output.append(day.get('description', 'Нет описания'))
            output.append("")
            output.append(f"**Цель**: {day.get('purpose', 'Не указана')}")
            output.append("")
        
        # Дни отдыха
        output.append("## 🛌 Дни отдыха")
        for day in plan.get('rest_days', []):
            output.append(f"### День {day.get('day', '?')} - {day.get('day_of_week', '?')} ({day.get('date', '?')})")
            output.append(f"**Активность**: {day.get('activity', 'Полный отдых')}")
            output.append(f"**Цель**: {day.get('purpose', 'Восстановление')}")
            output.append("")
        
        # Рекомендации
        recommendations = plan.get('recommendations', {})
        if recommendations:
            output.append("## 💡 Рекомендации")
            
            if 'nutrition' in recommendations:
                output.append("### 🍎 Питание")
                output.append(recommendations['nutrition'])
                output.append("")
                
            if 'recovery' in recommendations:
                output.append("### 🧘 Восстановление")
                output.append(recommendations['recovery'])
                output.append("")
                
            if 'progression' in recommendations:
                output.append("### 📈 Прогрессия")
                output.append(recommendations['progression'])
                output.append("")
                
            if 'adjustments' in recommendations:
                output.append("### 🔧 Корректировки")
                output.append(recommendations['adjustments'])
                output.append("")
        
        # Дата генерации
        output.append(f"---")
        output.append(f"План сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        return "\n".join(output)


# Пример использования инструмента напрямую:
if __name__ == "__main__":
    # Создаем экземпляр инструмента
    generate_plan_tool = GeneratePlanUseCase()
    
    # Пример профиля бегуна
    profile = RunnerProfile(
        age=35,
        gender="Мужской",
        weight=75.0,
        height=180.0,
        level="amateur",
        weekly_distance=30.0,
        goal_distance="21 км",
        goal_date="2025-08-15",
        available_days=["Понедельник", "Среда", "Пятница", "Воскресенье"],
        recent_runs=[
            RecentRun(date="2025-05-05", distance=8.5, pace="5:45"),
            RecentRun(date="2025-05-08", distance=10.0, pace="5:50")
        ]
    )
    
    # Генерируем план
    plan = generate_plan_tool(profile)
    
    # Выводим результат
    print(plan)
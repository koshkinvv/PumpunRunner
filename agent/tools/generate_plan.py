#!/usr/bin/env python3
"""
MCP-совместимый инструмент для генерации персонализированных тренировочных планов.
Этот модуль предоставляет класс GeneratePlanUseCase, который можно использовать как:
1. Самостоятельный компонент для генерации планов
2. Инструмент для OpenAI Assistants API
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pytz
from dataclasses import dataclass
from pydantic import BaseModel, Field


class RecentRun(BaseModel):
    """Модель для представления недавней тренировки бегуна."""
    date: str = Field(description="Дата тренировки в формате YYYY-MM-DD")
    distance: float = Field(description="Дистанция в километрах")
    pace: str = Field(description="Темп в формате MM:SS (минуты:секунды на километр)")
    notes: Optional[str] = Field(None, description="Заметки о тренировке (опционально)")


class TrainingDay(BaseModel):
    """Модель для представления дня тренировки в текущем плане."""
    day: str = Field(description="День недели")
    date: str = Field(description="Дата тренировки в формате DD.MM.YYYY")
    type: str = Field(description="Тип тренировки (например, Интервальная, Длительная)")
    distance: float = Field(description="Дистанция в километрах")
    completed: bool = Field(False, description="Отметка о выполнении тренировки")
    canceled: bool = Field(False, description="Отметка об отмене тренировки")


class CurrentPlan(BaseModel):
    """Модель для представления текущего плана тренировок."""
    description: str = Field(description="Описание плана тренировок")
    total_distance: float = Field(description="Общая дистанция плана в километрах")
    days: List[TrainingDay] = Field(description="Список дней тренировок")


class AdjustmentInfo(BaseModel):
    """Модель для представления информации о корректировке плана."""
    day_num: int = Field(description="Номер дня тренировки, который корректируется")
    training_type: str = Field(description="Тип тренировки")
    planned_distance: float = Field(description="Запланированная дистанция в километрах")
    actual_distance: float = Field(description="Фактически выполненная дистанция в километрах")
    difference_percent: float = Field(description="Процент разницы между планом и фактом")
    needs_adjustment: bool = Field(description="Требуется ли корректировка плана")


class RunnerProfile(BaseModel):
    """Модель профиля бегуна для генерации персонализированного плана тренировок."""
    age: Optional[int] = Field(None, description="Возраст бегуна")
    gender: Optional[str] = Field(None, description="Пол бегуна (Мужской/Женский)")
    weight: Optional[float] = Field(None, description="Вес бегуна в кг")
    height: Optional[float] = Field(None, description="Рост бегуна в см")
    level: Optional[str] = Field(None, description="Уровень подготовки (beginner, intermediate, advanced)")
    weekly_distance: Optional[float] = Field(None, description="Текущий еженедельный километраж")
    goal_distance: str = Field(description="Целевая дистанция (например, '5 км', '10 км', 'Полумарафон', 'Марафон')")
    goal_date: Optional[str] = Field(None, description="Дата целевого соревнования в формате YYYY-MM-DD")
    available_days: List[str] = Field(description="Список предпочтительных дней для тренировок (Понедельник, Вторник, и т.д.)")
    target_time: Optional[str] = Field(None, description="Целевое время финиша в формате HH:MM:SS или MM:SS")
    comfortable_pace: Optional[str] = Field(None, description="Комфортный темп бега в формате MM:SS (минуты:секунды на километр)")
    recent_runs: Optional[List[RecentRun]] = Field(None, description="Список недавних тренировок")
    # Новые поля для поддержки корректировки плана
    adjustment_info: Optional[AdjustmentInfo] = Field(None, description="Информация о корректировке плана")
    current_plan: Optional[CurrentPlan] = Field(None, description="Текущий план тренировок")
    # Поля для прямого управления поведением генерации плана
    force_adjustment_mode: Optional[bool] = Field(False, description="Принудительно использовать режим корректировки")
    explicit_adjustment_note: Optional[str] = Field(None, description="Явное текстовое описание корректировки для промпта")


class GeneratePlanUseCase:
    """
    MCP-совместимый инструмент для генерации персонализированных планов тренировок.
    
    Attributes:
        description: Описание инструмента для OpenAI Assistants API
        name: Название инструмента для OpenAI Assistants API
    """
    
    # MCP-совместимые атрибуты для использования с OpenAI Assistants API
    description = "Генерирует персонализированный план беговых тренировок на основе профиля бегуна"
    name = "generate_plan"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализирует генератор планов тренировок.
        
        Args:
            api_key: API ключ OpenAI (опционально)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API ключ OpenAI не предоставлен и не найден в переменных окружения")
        
        # Инициализируем клиент OpenAI с настройками таймаута
        from openai import OpenAI
        from httpx import Timeout
        # Настройка таймаута: 5 секунд на подключение, 120 секунд на чтение ответа
        timeout = Timeout(connect=5.0, read=120.0, write=10.0, pool=10.0)
        self.client = OpenAI(api_key=self.api_key, timeout=timeout)

        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
    
    def __call__(self, profile: RunnerProfile) -> Dict[str, Any]:
        """
        Генерирует персонализированный план тренировок на основе профиля бегуна.
        
        Args:
            profile: Профиль бегуна
        
        Returns:
            План тренировок в стандартном формате бота
        """
        # Конвертируем профиль в формат, подходящий для существующего кода бота
        bot_profile = self._convert_to_bot_profile(profile)
        
        # Генерируем план тренировок
        return self._generate_plan(bot_profile)
    
    def _convert_to_bot_profile(self, profile: RunnerProfile) -> Dict[str, Any]:
        """
        Конвертирует профиль из формата Pydantic в формат, используемый ботом.
        
        Args:
            profile: Профиль бегуна в формате Pydantic
        
        Returns:
            Профиль в формате, используемом ботом
        """
        # Определяем дни недели в правильном формате
        day_mapping = {
            "Понедельник": "пн",
            "Вторник": "вт",
            "Среда": "ср",
            "Четверг": "чт",
            "Пятница": "пт",
            "Суббота": "сб",
            "Воскресенье": "вс"
        }
        
        # Преобразуем предпочтительные дни в строку с сокращениями
        preferred_days = []
        for day in profile.available_days:
            for full_name, short_name in day_mapping.items():
                if day.lower().startswith(full_name.lower()):
                    preferred_days.append(short_name)
                    break
        
        preferred_days_str = ", ".join(preferred_days)
        
        # Создаем обратное отображение для еженедельного расстояния
        weekly_distance = profile.weekly_distance or 0
        
        # Определяем текст для даты соревнования
        competition_date = profile.goal_date or "Не указана"
        
        # Преобразуем дистанцию в числовой формат
        distance = 0
        if "марафон" in profile.goal_distance.lower():
            if "полу" in profile.goal_distance.lower():
                distance = 21.1
            else:
                distance = 42.2
        else:
            # Извлекаем числовое значение из строки
            import re
            distance_match = re.search(r'(\d+(?:\.\d+)?)', profile.goal_distance)
            if distance_match:
                distance = float(distance_match.group(1))
        
        # Создаем профиль в формате, используемом ботом
        bot_profile = {
            "distance": distance,
            "competition_date": competition_date,
            "gender": profile.gender or "Не указан",
            "age": profile.age or 0,
            "height": profile.height or 0,
            "weight": profile.weight or 0,
            "experience": profile.level or "Средний",
            "goal": "Улучшить время" if profile.target_time else "Закончить дистанцию",
            "target_time": profile.target_time or "",
            "comfortable_pace": profile.comfortable_pace or "",
            "weekly_volume": weekly_distance,
            "weekly_volume_text": f"{weekly_distance} км",
            "training_days_per_week": len(profile.available_days),
            "preferred_training_days": preferred_days_str,
            "training_start_date": datetime.now().strftime("%d.%m.%Y"),
            "training_start_date_text": "Сегодня"
        }
        
        return bot_profile
    
    def _generate_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует план тренировок с использованием OpenAI API.
        
        Args:
            profile: Профиль бегуна в формате, используемом ботом
        
        Returns:
            План тренировок в формате JSON
        """
        try:
            logging.info(f"Начинаем генерацию плана тренировок для пользователя с профилем: {profile}")
            
            # Получаем даты для тренировок
            dates_info = self._calculate_training_dates(profile)
            
            # Создаем системный промт на основе книг о тренировках
            system_prompt = self._get_expert_system_prompt(profile, dates_info)
            
            # Создаем пользовательский промт с профилем бегуна
            user_prompt = self._create_user_prompt(profile, dates_info)
            
            # Вызываем OpenAI API с увеличенным таймаутом
            logging.info("Отправляем запрос к OpenAI API (с таймаутом 120 секунд)")
            # Проверяем, содержит ли профиль информацию о корректировке или принудительный флаг
            adjustment_mode = False
            force_adjustment = False
            has_explicit_note = False
            
            try:
                # Проверяем наличие явной заметки о корректировке
                if isinstance(profile, dict):
                    has_explicit_note = profile.get('explicit_adjustment_note') is not None
                else:
                    has_explicit_note = getattr(profile, 'explicit_adjustment_note', None) is not None
                
                # Проверяем принудительный флаг
                if isinstance(profile, dict):
                    force_adjustment = profile.get('force_adjustment_mode', False)
                else:
                    force_adjustment = getattr(profile, 'force_adjustment_mode', False)
                    
                # Любой из этих признаков означает, что нужен режим корректировки
                if force_adjustment:
                    adjustment_mode = True
                    logging.info("Обнаружен принудительный флаг для режима корректировки плана")
                
                if has_explicit_note:
                    adjustment_mode = True
                    logging.info("Обнаружена явная заметка о корректировке плана")
                
                # Если предыдущие признаки не обнаружены, проверяем информацию о корректировке
                if not adjustment_mode:
                    # В зависимости от типа параметра проверяем разными способами
                    if isinstance(profile, dict):
                        # Если профиль - словарь
                        if profile.get('adjustment_info'):
                            adjustment_mode = True
                            logging.info("Запрос на корректировку плана (dict) - используем быстрый режим")
                    else:
                        # Если профиль - объект Pydantic
                        adjustment_info = getattr(profile, 'adjustment_info', None)
                        if adjustment_info:
                            adjustment_mode = True
                            logging.info("Запрос на корректировку плана (obj) - используем быстрый режим")
            except Exception as e:
                logging.warning(f"Ошибка при проверке режима корректировки: {e}")
            
            # Настраиваем параметры в зависимости от режима
            temperature = 1.0 if adjustment_mode else 0.7
            timeout = 180.0  # Увеличиваем таймаут для всех запросов
            
            # Всегда используем gpt-4o для всех запросов (в том числе корректировки)
            model = "gpt-4o"
            logging.info(f"Используем модель {model} для запроса (режим корректировки: {adjustment_mode})")
            
            logging.info(f"Отправляем запрос к OpenAI API (модель: {model}, таймаут: {timeout} секунд)")
            
            # Добавляем полное логирование промптов
            logging.info("SYSTEM PROMPT:")
            logging.info("=" * 80)
            logging.info(system_prompt[:1000] + "..." if len(system_prompt) > 1000 else system_prompt)
            logging.info("=" * 80)
            
            logging.info("USER PROMPT:")
            logging.info("=" * 80)
            logging.info(user_prompt)
            logging.info("=" * 80)
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                timeout=timeout
            )
            
            # Получаем и парсим ответ
            content = response.choices[0].message.content
            if content:
                plan_json = json.loads(content)
                logging.info(f"План успешно сгенерирован")
            else:
                raise ValueError("Пустой ответ от API OpenAI")
            
            return plan_json
            
        except Exception as e:
            logging.error(f"Ошибка при генерации плана тренировок: {e}")
            # Возвращаем базовый план в случае ошибки
            return self._generate_fallback_plan(profile)
    
    def _get_expert_system_prompt(self, profile: Dict[str, Any], dates_info: Dict[str, Any]) -> str:
        """
        Возвращает системный промпт с экспертными знаниями по тренировкам бега.
        
        Args:
            profile: Профиль бегуна
            dates_info: Информация о датах тренировок
            
        Returns:
            Системный промпт для OpenAI
        """
        # Формируем информацию о датах тренировок для промпта
        preferred_days_text = ", ".join(dates_info["preferred_days_names"])
        training_dates_info = "\n".join([
            f"- {date}: {weekday}" 
            for date, weekday in dates_info["training_dates_with_weekdays"].items()
        ])
        
        # Подготавливаем информацию о корректировке
        adjustment_note = ""
        try:
            if isinstance(profile, dict):
                explicit_note = profile.get('explicit_adjustment_note')
            else:
                explicit_note = getattr(profile, 'explicit_adjustment_note', None)
                
            if explicit_note:
                adjustment_note = f"⚠️ ВАЖНО! КОРРЕКТИРОВКА ПЛАНА: {explicit_note}\n\n"
                logging.info(f"Добавлена информация о корректировке в системный промпт")
        except Exception as e:
            logging.warning(f"Ошибка при подготовке информации о корректировке: {e}")
            
        # Системный промпт, основанный на экспертных знаниях о беговых тренировках
        return (
            f"Ты опытный беговой тренер, специалист по подготовке к соревнованиям на дистанции от 5км до марафона. "
            f"Твои знания основаны на методиках ведущих тренеров и научных исследованиях в области легкой атлетики и "
            f"спортивной физиологии (Jack Daniels, Pete Pfitzinger, Matt Fitzgerald, Brad Hudson, Arthur Lydiard, Steve Magness).\n\n"
            
            f"{adjustment_note}Твоя задача - создать персонализированный план тренировок для бегуна, используя ТОЛЬКО указанные даты "
            f"в точном соответствии с предпочтениями пользователя.\n\n"
            
            f"Пользователь выбрал следующие предпочитаемые дни недели для тренировок: {preferred_days_text}.\n"
            f"На основе этого выбора и указанной даты начала тренировок, были определены следующие даты тренировок:\n"
            f"{training_dates_info}\n\n"
            
            f"ВАЖНО: План тренировок должен включать ТОЛЬКО ЭТИ ДАТЫ и ДНИ НЕДЕЛИ. "
            f"НЕ ДОБАВЛЯЙ дополнительные дни тренировок кроме указанных выше дат.\n\n"
            
            f"План должен быть структурирован строго по этим дням недели с указанными датами.\n\n"
            
            f"Каждый день в плане должен обязательно содержать: день недели (например, 'Вторник'), "
            f"дату в формате ДД.ММ.YYYY (например, '07.05.2025'), тип тренировки, дистанцию, целевой темп "
            f"и детальное описание тренировки.\n\n"
            
            f"План должен включать все важные компоненты тренировочного процесса, соответствующие уровню бегуна: "
            f"- Для начинающих: легкие пробежки, run/walk интервалы, постепенное наращивание километража\n"
            f"- Для среднего уровня: темповые тренировки, фартлеки, длительные пробежки\n"
            f"- Для продвинутых: интервальные тренировки, специфичные темповые работы, периодизация\n\n"
            
            f"В зависимости от цели бегуна (целевая дистанция и время), адаптируй план, используя классические "
            f"принципы тренировок:\n"
            f"1. Периодичное увеличение нагрузки с циклами восстановления\n"
            f"2. Тренировка всех энергетических систем (аэробная, анаэробная)\n"
            f"3. Прогрессия интенсивности и объема\n"
            f"4. Специфичность тренировок под конкретную дистанцию\n\n"
            
            f"Учитывай цель бегуна, его физическую подготовку и еженедельный объем. Адаптируй тренировки так, "
            f"чтобы увеличение еженедельного объема не превышало 10% от текущего уровня.\n\n"
            
            f"Отвечай только в указанном JSON формате на русском языке."
        )
    
    def _create_user_prompt(self, profile: Dict[str, Any], dates_info: Dict[str, Any]) -> str:
        """
        Создает пользовательский промпт с профилем бегуна для запроса к OpenAI.
        
        Args:
            profile: Профиль бегуна
            dates_info: Информация о датах тренировок
            
        Returns:
            Пользовательский промпт
        """
        # Сначала проверяем наличие явной заметки о корректировке
        # Если есть, добавляем ее в начало промпта для лучшей видимости
        initial_note = ""
        try:
            if isinstance(profile, dict):
                explicit_note = profile.get('explicit_adjustment_note')
            else:
                explicit_note = getattr(profile, 'explicit_adjustment_note', None)
                
            if explicit_note:
                initial_note = f"⚠️ {explicit_note}\n\n"
                logging.info(f"В начало промпта добавлена явная заметка о корректировке")
        except Exception as e:
            logging.warning(f"Ошибка при обработке явной заметки для начала промпта: {e}")
            
        # Определяем начальную дату тренировок
        start_date = profile.get('training_start_date_text', profile.get('training_start_date', 'Сегодня'))
        
        # Проверяем, есть ли информация о корректировке плана
        is_adjustment = False
        try:
            # Проверяем принудительный режим корректировки
            force_adjustment = False
            if isinstance(profile, dict):
                force_adjustment = profile.get('force_adjustment_mode', False)
            else:
                force_adjustment = getattr(profile, 'force_adjustment_mode', False)
            
            # Проверяем наличие информации о корректировке
            has_adjustment_info = False
            if isinstance(profile, dict):
                has_adjustment_info = profile.get('adjustment_info') is not None
            else:
                adj_info = getattr(profile, 'adjustment_info', None)
                has_adjustment_info = adj_info is not None
                
            is_adjustment = force_adjustment or has_adjustment_info
            
            if is_adjustment:
                if force_adjustment:
                    logging.info("Применяется шаблон промпта для принудительной корректировки плана")
                else:
                    logging.info("Применяется шаблон промпта для корректировки плана")
        except Exception as e:
            logging.warning(f"Ошибка при определении типа промпта: {e}")
        
        # Для корректировки используем более компактный промпт
        if is_adjustment:
            # Получаем объект adjustment_info в зависимости от типа профиля
            adj_info = None
            if isinstance(profile, dict):
                adj_info = profile.get('adjustment_info', {})
            else:
                adj_info = getattr(profile, 'adjustment_info', None)
            # Получаем информацию о корректировке
            day_num = 0
            training_type = "неизвестно"
            actual_distance = 0
            planned_distance = 0
            difference_percent = 0
            
            try:
                if isinstance(adj_info, dict):
                    day_num = adj_info.get('day_num', 0)
                    training_type = adj_info.get('training_type', 'неизвестно')
                    actual_distance = adj_info.get('actual_distance', 0)
                    planned_distance = adj_info.get('planned_distance', 0)
                    difference_percent = adj_info.get('difference_percent', 0)
                else:
                    day_num = getattr(adj_info, 'day_num', 0)
                    training_type = getattr(adj_info, 'training_type', 'неизвестно')
                    actual_distance = getattr(adj_info, 'actual_distance', 0)
                    planned_distance = getattr(adj_info, 'planned_distance', 0)
                    difference_percent = getattr(adj_info, 'difference_percent', 0)
            except Exception as e:
                logging.warning(f"Ошибка при получении данных о корректировке: {e}")
            
            # Более короткий промпт для быстрой корректировки плана
            # Добавляем "⚠️" в начало для привлечения внимания
            prompt = initial_note + (
                f"Корректировка плана тренировок для бегуна. Профиль бегуна:\n"
                f"- Дистанция: {profile.get('distance', 'Неизвестно')} км\n"
                f"- Уровень: {profile.get('experience', 'intermediate')}\n"
                f"- Еженедельный объем: {profile.get('weekly_volume', 'Неизвестно')} км\n"
                f"- Комфортный темп: {profile.get('comfortable_pace', 'Неизвестно')}\n\n"
                
                f"⚠️ КОРРЕКТИРОВКА ПЛАНА: В день {day_num} ({training_type}) "
                f"спортсмен пробежал {actual_distance} км вместо запланированных {planned_distance} км "
                f"(разница примерно {difference_percent:.1f}%). "
            )
            
            # Проверяем значения actual_distance и planned_distance
            try:
                # Actual_distance и planned_distance уже получены выше
                if float(actual_distance) < float(planned_distance):
                    prompt += f"Спортсмен не достиг целевой дистанции, следует немного снизить нагрузку в следующих тренировках.\n\n"
                else:
                    prompt += f"Спортсмен превысил целевую дистанцию, можно немного увеличить нагрузку, но не более 10%.\n\n"
            except Exception as e:
                logging.warning(f"Ошибка при сравнении дистанций: {e}")
                prompt += f"Необходимо скорректировать план с учетом последней тренировки.\n\n"
            
            # Добавляем информацию о текущем плане, если она есть
            has_current_plan = False
            current_plan_days = 0
            current_plan_distance = 0
            
            try:
                if isinstance(profile, dict) and profile.get('current_plan'):
                    has_current_plan = True
                    current_plan = profile.get('current_plan', {})
                    current_plan_days = len(current_plan.get('days', []))
                    current_plan_distance = current_plan.get('total_distance', 0)
                elif hasattr(profile, 'current_plan') and profile.current_plan:
                    has_current_plan = True
                    current_plan_days = len(profile.current_plan.days)
                    current_plan_distance = profile.current_plan.total_distance
                
                if has_current_plan:
                    prompt += f"Текущий план содержит {current_plan_days} тренировок на общую дистанцию {current_plan_distance} км.\n\n"
            except Exception as e:
                logging.warning(f"Ошибка при обработке информации о текущем плане: {e}")
            
            prompt += (
                "Создай скорректированный план тренировок, учитывая эту информацию. "
                "План должен включать разнообразные тренировки с учетом уровня подготовки бегуна.\n\n"
            )
        else:
            # Стандартный промпт для обычной генерации плана
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
                f"- Комфортный темп бега: {profile.get('comfortable_pace', 'Неизвестно')}\n"
                f"- Еженедельный объем бега: {profile.get('weekly_volume_text', profile.get('weekly_volume', 'Неизвестно'))} км\n\n"
            )
            
            # Проверяем наличие явной заметки о корректировке
            explicit_note = None
            try:
                if isinstance(profile, dict):
                    explicit_note = profile.get('explicit_adjustment_note')
                else:
                    explicit_note = getattr(profile, 'explicit_adjustment_note', None)
                    
                if explicit_note:
                    # Добавляем явную заметку о корректировке в промпт
                    prompt += f"\n{explicit_note}\n\n"
                    logging.info(f"Добавлена явная заметка о корректировке в промпт: {explicit_note}")
            except Exception as e:
                logging.warning(f"Ошибка при обработке явной заметки о корректировке: {e}")
            
            # Проверяем, есть ли информация о корректировке плана, но не требуется серьезной корректировки
            if hasattr(profile, 'adjustment_info') and profile.adjustment_info:
                adj_info = profile.adjustment_info
                prompt += (
                    f"Примечание: В дне {adj_info.day_num} была небольшая разница между планом и фактом "
                    f"({adj_info.actual_distance} км вместо {adj_info.planned_distance} км), "
                    f"но серьезной корректировки не требуется.\n\n"
                )
            
            # Добавляем информацию о текущем плане, если она есть
            if hasattr(profile, 'current_plan') and profile.current_plan:
                prompt += (
                    f"Примечание: Текущий план содержит {len(profile.current_plan.days)} тренировок "
                    f"на общую дистанцию {profile.current_plan.total_distance} км.\n\n"
                )
                
        # Общая часть промпта для обоих случаев
        prompt += (
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
            '      "date": "Дата в формате ДД.ММ.YYYY",\n'
            '      "training_type": "Тип тренировки (например, Длительная, Интервальная, Восстановительная)",\n'
            '      "distance": "Дистанция (например, 5 км)",\n'
            '      "pace": "Целевой темп (например, 5:30/км)",\n'
            '      "description": "Детальное описание тренировки",\n'
            '      "purpose": "Цель тренировки"\n'
            '    },\n'
            '    ...\n'
            '  ]\n'
            '}'
        )
        
        return prompt
    
    def _calculate_training_dates(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитывает даты тренировок на основе предпочтений из профиля.
        
        Args:
            profile: Профиль бегуна
            
        Returns:
            Dict: Информация о датах тренировок
        """
        # Используем Московское время (UTC+3)
        moscow_tz = pytz.timezone('Europe/Moscow')
        
        # Проверяем, указал ли пользователь дату начала тренировок
        user_start_date = profile.get('training_start_date_text', profile.get('training_start_date', None))
        
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
        preferred_days_str = profile.get('preferred_training_days', '')
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
        training_days_count = int(profile.get('training_days_per_week', 3))
        
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
        
        # Получаем словарь дат тренировок с днями недели
        training_dates_with_weekdays = {}
        for date in training_dates:
            weekday_num = date.weekday()
            weekday_name = day_number_to_name[weekday_num]
            date_str = date.strftime("%d.%m.%Y")
            training_dates_with_weekdays[date_str] = weekday_name
        
        return {
            "dates": dates,
            "first_day": dates[0] if dates else None,
            "second_day": dates[1] if len(dates) > 1 else None,
            "preferred_days": preferred_days,
            "preferred_days_names": preferred_days_names,
            "training_dates_with_weekdays": training_dates_with_weekdays
        }
    
    def _generate_fallback_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует простой план тренировок в случае ошибки основного метода.
        
        Args:
            profile: Профиль бегуна
            
        Returns:
            Простой план тренировок в формате JSON
        """
        # Получаем сегодняшнюю дату и день недели
        today = datetime.now()
        weekday = today.weekday()
        
        # Определяем дни недели
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        # Генерируем даты для плана, начиная с сегодняшнего дня
        dates = [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(7)]
        
        # Создаем простой план тренировок
        distance = float(profile.get('distance', 5))
        weekly_volume = float(profile.get('weekly_volume', 20))
        
        # Подстраиваем план под еженедельный объем
        run_distances = [3, 5, 3, 0, 0, 8, 0]  # Базовые дистанции
        
        # Масштабируем дистанции в соответствии с еженедельным объемом
        total_base = sum(run_distances)
        scaling_factor = weekly_volume / total_base if total_base > 0 else 1
        run_distances = [round(d * scaling_factor, 1) for d in run_distances]
        
        # Генерируем тренировочные дни
        training_days = []
        for i in range(7):
            day_idx = (weekday + i) % 7
            day = days[day_idx]
            date = dates[i]
            
            if run_distances[day_idx] > 0:
                if day_idx == 5:  # Суббота - длительная
                    training_type = "Длительная пробежка"
                    pace = "6:00-6:30/км"
                    description = (
                        "Разминка: 10 минут легкого бега в комфортном темпе.\n"
                        "Основная часть: Бег в равномерном темпе на всей дистанции. Сфокусируйтесь на ровном дыхании и правильной технике.\n"
                        "Заминка: 5 минут легкого бега и растяжка."
                    )
                    purpose = "Развитие общей выносливости и аэробной базы"
                elif day_idx == 0 or day_idx == 2:  # Пн, Ср - восстановительные
                    training_type = "Восстановительная пробежка"
                    pace = "6:30-7:00/км"
                    description = (
                        "Разминка: 5 минут ходьбы.\n"
                        "Основная часть: Легкий бег в комфортном темпе. Сфокусируйтесь на расслаблении и восстановлении.\n"
                        "Заминка: Растяжка основных мышечных групп."
                    )
                    purpose = "Восстановление и поддержание объема"
                else:  # Остальные дни
                    training_type = "Пробежка в среднем темпе"
                    pace = "5:45-6:15/км"
                    description = (
                        "Разминка: 10 минут легкого бега и динамическая разминка.\n"
                        "Основная часть: Бег в среднем темпе. Сфокусируйтесь на поддержании постоянного темпа.\n"
                        "Заминка: 5 минут легкого бега и растяжка."
                    )
                    purpose = "Развитие выносливости и привыкание к оптимальному темпу"
                
                training_days.append({
                    "day": day,
                    "date": date,
                    "training_type": training_type,
                    "distance": f"{run_distances[day_idx]} км",
                    "pace": pace,
                    "description": description,
                    "purpose": purpose
                })
        
        # Создаем план
        return {
            "plan_name": f"Базовый план для подготовки к {distance} км",
            "plan_description": (
                f"Этот план разработан для постепенной подготовки к дистанции {distance} км. "
                f"План включает длительные пробежки для развития выносливости, восстановительные дни "
                f"и пробежки в среднем темпе для улучшения аэробной базы."
            ),
            "training_days": training_days
        }
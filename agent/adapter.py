"""
Адаптер для интеграции MCP-инструментов с существующим ботом.
Позволяет использовать новые инструменты, сохраняя обратную совместимость.
"""

import logging
from typing import Dict, Any, Optional, List

from .tools.generate_plan import GeneratePlanUseCase, RunnerProfile, RecentRun


class AgentAdapter:
    """
    Адаптер для интеграции MCP-совместимых инструментов с существующим ботом.
    """
    
    def __init__(self):
        """Инициализирует адаптер."""
        # Инициализируем инструменты при первом использовании
        self._generate_plan_tool = None
        
    def generate_training_plan_continuation(self, runner_profile: Dict[str, Any], total_distance: float, 
                                  current_plan: Dict[str, Any], 
                                  force_adjustment_mode: bool = False, 
                                  explicit_adjustment_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Генерирует продолжение тренировочного плана на основе уже выполненных тренировок.
        
        Этот метод имитирует интерфейс существующего OpenAIService.generate_training_plan_continuation,
        но использует новый MCP-инструмент для генерации планов.
        
        Args:
            runner_profile: Профиль бегуна
            total_distance: Общая пройденная дистанция 
            current_plan: Текущий план тренировок
            force_adjustment_mode: Принудительно использовать режим корректировки
            explicit_adjustment_note: Явное текстовое описание корректировки для промпта
            
        Returns:
            Новый план тренировок в формате, совместимом с ботом
        """
        try:
            logging.info(f"AgentAdapter: Запуск генерации продолжения плана через MCP-инструмент")
            
            # Инициализируем инструмент при первом использовании
            if self._generate_plan_tool is None:
                self._generate_plan_tool = GeneratePlanUseCase()
                logging.info("AgentAdapter: Инициализирован инструмент GeneratePlanUseCase")
            
            # Преобразуем профиль бота в формат, подходящий для MCP-инструмента
            mcp_profile = self._convert_to_mcp_profile(runner_profile)
            
            # Добавляем информацию о выполненных тренировках в профиль
            mcp_profile.recent_runs = self._extract_completed_trainings(current_plan, total_distance)
            
            # Проверяем дополнительные параметры
            if force_adjustment_mode:
                # Принудительно устанавливаем флаг корректировки
                mcp_profile_dict = mcp_profile.model_dump()
                mcp_profile_dict['force_adjustment_mode'] = True
                mcp_profile = RunnerProfile(**mcp_profile_dict)
                logging.info(f"AgentAdapter: Установлен принудительный режим корректировки")
                
            if explicit_adjustment_note:
                # Добавляем явную заметку о корректировке
                mcp_profile_dict = mcp_profile.model_dump()
                mcp_profile_dict['explicit_adjustment_note'] = explicit_adjustment_note
                mcp_profile = RunnerProfile(**mcp_profile_dict)
                logging.info(f"AgentAdapter: Добавлена явная заметка о корректировке для продолжения плана")
            
            logging.info(f"AgentAdapter: Профиль с выполненными тренировками преобразован в MCP-формат")
            
            # Генерируем новый план с учетом предыдущих тренировок
            plan = self._generate_plan_tool(mcp_profile)
            logging.info(f"AgentAdapter: Продолжение плана успешно сгенерировано через MCP-инструмент")
            
            return plan
            
        except Exception as e:
            logging.error(f"AgentAdapter: Ошибка при генерации продолжения плана: {e}")
            # В случае ошибки делегируем генерацию плана оригинальному сервису
            from openai_service import OpenAIService
            logging.info(f"AgentAdapter: Переключение на оригинальный OpenAIService для генерации продолжения плана")
            openai_service = OpenAIService()
            return openai_service.generate_training_plan_continuation(runner_profile, total_distance, current_plan)
            
    def _extract_completed_trainings(self, current_plan: Dict[str, Any], total_distance: float) -> List[RecentRun]:
        """
        Извлекает информацию о выполненных тренировках из текущего плана.
        
        Args:
            current_plan: Текущий план тренировок
            total_distance: Общая пройденная дистанция
            
        Returns:
            Список выполненных тренировок в формате RecentRun
        """
        recent_runs = []
        
        try:
            # Получаем тренировочные дни из текущего плана
            training_days = current_plan.get('training_days', [])
            completed_days = []
            
            # Ищем выполненные тренировки
            for day_idx, day in enumerate(training_days):
                # Проверяем, была ли тренировка отмечена как выполненная
                day_num = day_idx + 1
                if f"completed_{day_num}" in current_plan.get('completed_trainings', {}):
                    completed_days.append(day)
            
            # Преобразуем выполненные тренировки в формат RecentRun
            for day in completed_days:
                try:
                    date_str = day.get('date', '')
                    # Преобразуем формат даты из DD.MM.YYYY в YYYY-MM-DD
                    if date_str:
                        date_parts = date_str.split('.')
                        if len(date_parts) == 3:
                            date_str = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
                    
                    # Получаем дистанцию
                    distance_str = day.get('distance', '0')
                    distance = 0.0
                    
                    # Извлекаем числовое значение дистанции
                    import re
                    distance_match = re.search(r'(\d+(?:\.\d+)?)', str(distance_str))
                    if distance_match:
                        distance = float(distance_match.group(1))
                    
                    # Получаем темп
                    pace = day.get('pace', '0:00')
                    
                    # Добавляем выполненную тренировку
                    if date_str and distance > 0:
                        recent_runs.append(
                            RecentRun(
                                date=date_str,
                                distance=distance,
                                pace=pace,
                                notes=f"Тренировка из предыдущего плана: {day.get('training_type', '')}"
                            )
                        )
                except Exception as e:
                    logging.error(f"Ошибка при обработке выполненной тренировки: {e}")
            
            logging.info(f"Извлечено {len(recent_runs)} выполненных тренировок из текущего плана")
            
        except Exception as e:
            logging.error(f"Ошибка при извлечении выполненных тренировок: {e}")
        
        return recent_runs
    
    def generate_training_plan(self, runner_profile: Dict[str, Any], 
                         force_adjustment_mode: bool = False, 
                         explicit_adjustment_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Генерирует план тренировок с использованием MCP-инструмента.
        
        Этот метод имитирует интерфейс существующего OpenAIService.generate_training_plan,
        но использует новый MCP-инструмент для генерации планов.
        
        Args:
            runner_profile: Профиль бегуна в формате, используемом ботом
            force_adjustment_mode: Принудительно использовать режим корректировки
            explicit_adjustment_note: Явное текстовое описание корректировки для промпта
            
        Returns:
            План тренировок в формате, совместимом с ботом
        """
        try:
            logging.info(f"AgentAdapter: Запуск генерации плана тренировок через MCP-инструмент")
            
            # Инициализируем инструмент при первом использовании
            if self._generate_plan_tool is None:
                self._generate_plan_tool = GeneratePlanUseCase()
                logging.info("AgentAdapter: Инициализирован инструмент GeneratePlanUseCase")
            
            # Преобразуем профиль бота в формат, подходящий для MCP-инструмента
            mcp_profile = self._convert_to_mcp_profile(runner_profile)
            logging.info(f"AgentAdapter: Профиль преобразован в MCP-формат с целевой дистанцией {mcp_profile.goal_distance}")
            
            # Проверяем дополнительные параметры
            if force_adjustment_mode:
                # Принудительно устанавливаем флаг корректировки
                mcp_profile_dict = mcp_profile.model_dump()
                mcp_profile_dict['force_adjustment_mode'] = True
                mcp_profile = RunnerProfile(**mcp_profile_dict)
                logging.info(f"AgentAdapter: Установлен принудительный режим корректировки")
                
            if explicit_adjustment_note:
                # Добавляем явную заметку о корректировке
                mcp_profile_dict = mcp_profile.model_dump()
                mcp_profile_dict['explicit_adjustment_note'] = explicit_adjustment_note
                mcp_profile = RunnerProfile(**mcp_profile_dict)
                logging.info(f"AgentAdapter: Добавлена явная заметка о корректировке для нового плана")
            
            # Генерируем план
            plan = self._generate_plan_tool(mcp_profile)
            logging.info(f"AgentAdapter: План успешно сгенерирован через MCP-инструмент")
            
            return plan
            
        except Exception as e:
            logging.error(f"AgentAdapter: Ошибка при генерации плана тренировок: {e}")
            # В случае ошибки делегируем генерацию плана оригинальному сервису
            from openai_service import OpenAIService
            logging.info(f"AgentAdapter: Переключение на оригинальный OpenAIService для генерации плана")
            openai_service = OpenAIService()
            return openai_service.generate_training_plan(runner_profile)
    
    def adjust_training_plan(self, runner_profile: Dict[str, Any], current_plan: Dict[str, Any], 
                       day_num: int, planned_distance: float, actual_distance: float,
                       force_adjustment_mode: bool = False, explicit_adjustment_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Корректирует тренировочный план на основе фактических результатов выполнения тренировки.
        
        Этот метод имитирует интерфейс существующего OpenAIService.adjust_training_plan,
        но использует MCP-инструмент для корректировки планов.
        
        Args:
            runner_profile: Профиль бегуна
            current_plan: Текущий план тренировок
            day_num: Номер дня тренировки, который корректируется
            planned_distance: Запланированная дистанция
            actual_distance: Фактически выполненная дистанция
            force_adjustment_mode: Принудительно использовать режим корректировки
            explicit_adjustment_note: Явное текстовое описание корректировки для промпта
            
        Returns:
            Скорректированный план тренировок
        """
        try:
            logging.info(f"AgentAdapter: Запуск корректировки плана через MCP-инструмент")
            
            # Инициализируем инструмент при первом использовании
            if self._generate_plan_tool is None:
                self._generate_plan_tool = GeneratePlanUseCase()
                logging.info("AgentAdapter: Инициализирован инструмент GeneratePlanUseCase для корректировки плана")
            
            # Преобразуем профиль бота в формат, подходящий для MCP-инструмента
            mcp_profile = self._convert_to_mcp_profile(runner_profile)
            
            # Добавляем информацию о тренировке, которую нужно скорректировать
            difference_percent = abs(actual_distance - planned_distance) / planned_distance * 100 if planned_distance > 0 else 0
            
            # Получаем день тренировки, который нужно скорректировать
            training_days = current_plan.get('training_days', [])
            if 0 < day_num <= len(training_days):
                day_to_adjust = training_days[day_num - 1]
                logging.info(f"День для корректировки: {day_to_adjust.get('day', 'Неизвестно')} - {day_to_adjust.get('training_type', 'Неизвестно')}")
                
                # Если разница больше 20%, добавляем специальную информацию в профиль
                adjustment_info = {
                    "day_num": day_num,
                    "training_type": day_to_adjust.get('training_type', ''),
                    "planned_distance": planned_distance,
                    "actual_distance": actual_distance,
                    "difference_percent": difference_percent,
                    "needs_adjustment": difference_percent > 20
                }
                
                # Создаем модели AdjustmentInfo и CurrentPlan для профиля бегуна
                from agent.tools.generate_plan import AdjustmentInfo, CurrentPlan, TrainingDay
                
                # Создаем экземпляр AdjustmentInfo
                adj_info = AdjustmentInfo(
                    day_num=day_num,
                    training_type=day_to_adjust.get('training_type', ''),
                    planned_distance=planned_distance,
                    actual_distance=actual_distance,
                    difference_percent=difference_percent,
                    needs_adjustment=difference_percent > 20
                )
                
                # Создаем список моделей TrainingDay
                training_day_models = []
                for day in training_days:
                    training_day_models.append(TrainingDay(
                        day=day.get('day', ''),
                        date=day.get('date', ''),
                        type=day.get('training_type', ''),
                        distance=day.get('distance', 0),
                        completed=day.get('completed', False),
                        canceled=day.get('canceled', False)
                    ))
                
                # Создаем экземпляр CurrentPlan
                curr_plan = CurrentPlan(
                    description=current_plan.get('plan_description', ''),
                    total_distance=current_plan.get('total_distance', 0),
                    days=training_day_models
                )
                
                # Добавляем информацию к профилю бегуна
                mcp_profile_dict = mcp_profile.model_dump()
                mcp_profile_dict['adjustment_info'] = adj_info.model_dump()
                mcp_profile_dict['current_plan'] = curr_plan.model_dump()
                
                # Создаем новый экземпляр RunnerProfile с добавленной информацией
                from agent.tools.generate_plan import RunnerProfile
                mcp_profile = RunnerProfile(**mcp_profile_dict)
                
                logging.info(f"Информация для корректировки: разница {difference_percent:.1f}% между планом и фактом")
                
                # Принудительно устанавливаем флаг корректировки, если передан соответствующий параметр
                # или по умолчанию для автоматического использования быстрой модели
                mcp_profile_dict = mcp_profile.model_dump()
                mcp_profile_dict['force_adjustment_mode'] = force_adjustment_mode or True  # По умолчанию включаем
                mcp_profile = RunnerProfile(**mcp_profile_dict)
                
                # Добавляем явную информацию о корректировке
                # Сначала проверяем, передана ли явная заметка в параметрах
                if explicit_adjustment_note:
                    # Используем переданную заметку
                    mcp_profile_dict = mcp_profile.model_dump()
                    mcp_profile_dict['explicit_adjustment_note'] = explicit_adjustment_note
                    mcp_profile = RunnerProfile(**mcp_profile_dict)
                    logging.info(f"Использована явная заметка о корректировке из параметров")
                elif not hasattr(mcp_profile, 'explicit_adjustment_note'):
                    # Создаем строковое описание корректировки для промпта
                    adj_note = (f"ТРЕБУЕТСЯ КОРРЕКТИРОВКА ПЛАНА: В день {day_num} (тренировка {day_to_adjust.get('training_type', '')}) "
                               f"пользователь пробежал {actual_distance} км вместо запланированных {planned_distance} км. "
                               f"Разница составляет {difference_percent:.1f}%. "
                               f"Пожалуйста, скорректируйте тренировки с учетом этого отклонения.")
                    
                    # Добавляем в словарь модели
                    mcp_profile_dict = mcp_profile.model_dump()
                    mcp_profile_dict['explicit_adjustment_note'] = adj_note
                    mcp_profile = RunnerProfile(**mcp_profile_dict)
                    logging.info(f"Создана автоматическая заметка о корректировке")
                
                # Дополнительное логирование для отладки
                logging.info(f"Проверяем профиль MCP перед отправкой: "
                            f"adjustment_info={getattr(mcp_profile, 'adjustment_info', 'Нет')}, "
                            f"force_adjustment_mode={getattr(mcp_profile, 'force_adjustment_mode', 'Нет')}")
                
                # У MCP нет специального метода для корректировки, поэтому используем generate_training_plan
                # и передаем информацию о корректировке через профиль
                logging.info("Запускаем корректировку плана в режиме FAST с упрощенным промптом")
                adjusted_plan = self._generate_plan_tool(mcp_profile)
                
                # Проверяем, что план сгенерирован корректно
                if not adjusted_plan:
                    logging.warning("MCP-инструмент вернул пустой план, используем резервный вариант")
                    from openai_service import OpenAIService
                    openai_service = OpenAIService()
                    adjusted_plan = openai_service.adjust_training_plan(runner_profile, current_plan, day_num, planned_distance, actual_distance)
                else:
                    # Обновляем описание в плане, чтобы указать корректировку
                    if "plan_description" in adjusted_plan:
                        adjusted_plan["plan_description"] += f"\n\nПлан скорректирован с учетом фактического выполнения тренировки {day_num} ({actual_distance} км вместо {planned_distance} км)."
                
                logging.info(f"План успешно скорректирован через MCP-инструмент")
                
                # Гарантируем, что возвращаем словарь
                return adjusted_plan if adjusted_plan else {
                    "plan_name": "Скорректированный план тренировок",
                    "plan_description": f"План был скорректирован с учетом фактического выполнения тренировки {day_num}.",
                    "training_days": current_plan.get('training_days', []),
                    "total_distance": current_plan.get('total_distance', 0)
                }
            else:
                logging.error(f"Некорректный номер дня тренировки: {day_num}, всего дней: {len(training_days)}")
                raise ValueError(f"Некорректный номер дня тренировки: {day_num}")
                
        except Exception as e:
            logging.error(f"AgentAdapter: Ошибка при корректировке плана тренировок: {e}")
            # В случае ошибки делегируем корректировку плана оригинальному сервису
            from openai_service import OpenAIService
            logging.info(f"AgentAdapter: Переключение на оригинальный OpenAIService для корректировки плана")
            openai_service = OpenAIService()
            fallback_plan = openai_service.adjust_training_plan(runner_profile, current_plan, day_num, planned_distance, actual_distance)
            
            # Гарантируем, что возвращаем словарь даже при сбое резервного метода
            if fallback_plan:
                return fallback_plan
            else:
                logging.error("Критическая ошибка: Оба метода корректировки не смогли создать план. Возвращаем базовый план.")
                return {
                    "plan_name": "Запасной план тренировок",
                    "plan_description": f"План был создан автоматически из-за ошибки в системе корректировки.",
                    "training_days": current_plan.get('training_days', []),
                    "total_distance": current_plan.get('total_distance', 0)
                }
    
    def _convert_to_mcp_profile(self, bot_profile: Dict[str, Any]) -> RunnerProfile:
        """
        Преобразует профиль из формата бота в формат MCP-инструмента.
        
        Args:
            bot_profile: Профиль бегуна в формате, используемом ботом
            
        Returns:
            Профиль в формате, используемом MCP-инструментом
        """
        # Получаем предпочитаемые дни тренировок
        preferred_days_str = bot_profile.get('preferred_training_days', '')
        short_to_full = {
            'пн': 'Понедельник',
            'вт': 'Вторник',
            'ср': 'Среда',
            'чт': 'Четверг',
            'пт': 'Пятница',
            'сб': 'Суббота',
            'вс': 'Воскресенье'
        }
        
        # Преобразуем сокращения в полные названия дней
        preferred_days = []
        if preferred_days_str:
            for day in preferred_days_str.lower().split(','):
                day = day.strip()
                if day in short_to_full:
                    preferred_days.append(short_to_full[day])
        
        # Если дни не указаны, используем стандартные дни (Пн, Ср, Сб)
        if not preferred_days:
            preferred_days = ['Понедельник', 'Среда', 'Суббота']
        
        # Преобразуем целевую дистанцию в правильный формат
        distance = bot_profile.get('goal_distance', 5)
        goal_distance = f"{distance} км"
        
        if distance == 21.1:
            goal_distance = "Полумарафон"
        elif distance == 42.2:
            goal_distance = "Марафон"
        
        # Создаем профиль в формате MCP-инструмента
        return RunnerProfile(
            age=bot_profile.get('age'),
            gender=bot_profile.get('gender'),
            weight=bot_profile.get('weight'),
            height=bot_profile.get('height'),
            level=bot_profile.get('experience', 'intermediate'),
            weekly_distance=bot_profile.get('weekly_volume'),
            goal_distance=goal_distance,
            goal_date=bot_profile.get('competition_date'),
            available_days=preferred_days,
            target_time=bot_profile.get('target_time'),
            comfortable_pace=bot_profile.get('comfortable_pace'),
            recent_runs=[],  # Пустой список недавних тренировок
            adjustment_info=None,  # По умолчанию нет информации о корректировке
            current_plan=None  # По умолчанию нет текущего плана
        )
import logging

def format_training_day(day, training_day_num):
    """
    Улучшенная функция для форматирования дня тренировки.
    Отображает расширенную информацию, включая пульсовые зоны, детальное описание,
    рекомендации по питанию и восстановлению.
    
    Args:
        day: Словарь с данными о дне тренировки
        training_day_num: Номер дня тренировки
        
    Returns:
        str: Отформатированное сообщение о дне тренировки
    """
    try:
        # Проверяем, что день является словарем
        if not isinstance(day, dict):
            logging.error(f"Ошибка формата дня тренировки: {type(day)}, значение: {day}")
            # Возвращаем стандартный день тренировки
            return (
                f"*День {training_day_num}*\n"
                f"Тип: Легкая пробежка\n"
                f"Дистанция: 5 км\n"
                f"Темп: 6:00-6:30 мин/км\n\n"
                f"🔄 Разминка: Легкий бег 10-15 минут\n\n"
                f"🏃 Основная часть: Легкая пробежка в комфортном темпе\n\n"
                f"🧘 Заминка: Легкий бег 5 минут и растяжка"
            )
        
        # Основные данные о дне тренировки
        try:
            # Собираем основную информацию
            day_date = day.get('date', 'Дата не указана')
            day_name = day.get('day', day.get('day_of_week', f'День {training_day_num}'))
            
            # Поддержка различных форматов типа тренировки
            training_type = None
            for field in ['training_type', 'type', 'workout_type']:
                if field in day and day[field]:
                    training_type = day[field]
                    break
            if not training_type:
                training_type = 'Тип не указан'
            
            # Дистанция и темп
            distance = day.get('distance', 'Дистанция не указана')
            pace = day.get('pace', 'Темп не указан')
            
            # Пульсовые зоны
            heart_rate = day.get('heart_rate', '')
            heart_rate_text = f"\nПульс: {heart_rate}" if heart_rate else ""
            
            # Детальное описание тренировки
            description = day.get('description', '')
            purpose = day.get('purpose', '')
            
            # Получаем поля для структурированного описания
            workout_segments = day.get('workout_segments', {})
            warmup_segment = workout_segments.get('warmup', '')
            main_segment = workout_segments.get('main', '')
            cooldown_segment = workout_segments.get('cooldown', '')
            
            # Дополнительные поля
            nutrition = day.get('nutrition', '')
            recovery = day.get('recovery', '')
            notes = day.get('notes', '')
            
            # Также поддерживаем прямые поля
            direct_warmup = day.get('warmup', '')
            direct_main = day.get('main_part', '')
            direct_cooldown = day.get('cooldown', '')
            
            # Используем данные из структуры или прямых полей
            warmup = warmup_segment or direct_warmup
            main_part = main_segment or direct_main
            cooldown = cooldown_segment or direct_cooldown
            
        except Exception as e:
            logging.exception(f"Ошибка при извлечении базовых данных: {e}")
            return (
                f"*День {training_day_num}*\n"
                f"Тип: Легкая пробежка\n"
                f"Дистанция: 5 км\n"
                f"Темп: 6:00-6:30 мин/км\n\n"
                f"🔄 Разминка: Легкий бег 10-15 минут\n\n"
                f"🏃 Основная часть: Легкая пробежка в комфортном темпе\n\n"
                f"🧘 Заминка: Легкий бег 5 минут и растяжка"
            )
        
        # Формируем структурированное описание тренировки
        try:
            description_parts = []
            
            # 1. Используем данные из полей warmup, main_part, cooldown если они есть
            if warmup or main_part or cooldown:
                if warmup:
                    description_parts.append(f"🔄 Разминка: {warmup}")
                else:
                    description_parts.append(f"🔄 Разминка: Легкий бег в комфортном темпе 10-15 минут")
                
                if main_part:
                    description_parts.append(f"🏃 Основная часть: {main_part}")
                elif description:
                    description_parts.append(f"🏃 Основная часть: {description}")
                else:
                    description_parts.append(f"🏃 Основная часть: Бег в указанном темпе")
                
                if cooldown:
                    description_parts.append(f"🧘 Заминка: {cooldown}")
                else:
                    description_parts.append(f"🧘 Заминка: Легкий бег 5-10 минут и растяжка")
                
            # 2. Проверяем, есть ли структурированное описание в описании
            elif description and ("Разминка:" in description or "Основная часть:" in description or "Заминка:" in description):
                # Извлекаем разминку
                if "Разминка:" in description:
                    try:
                        warmup_text = description.split("Разминка:")[1].split("Основная часть:")[0].strip() if "Основная часть:" in description else description.split("Разминка:")[1].strip()
                        description_parts.append(f"🔄 Разминка: {warmup_text}")
                    except Exception:
                        description_parts.append("🔄 Разминка: Легкий бег в комфортном темпе 10-15 минут")
                else:
                    description_parts.append("🔄 Разминка: Легкий бег в комфортном темпе 10-15 минут")
                
                # Извлекаем основную часть
                if "Основная часть:" in description:
                    try:
                        main_text = description.split("Основная часть:")[1].split("Заминка:")[0].strip() if "Заминка:" in description else description.split("Основная часть:")[1].strip()
                        description_parts.append(f"🏃 Основная часть: {main_text}")
                    except Exception:
                        description_parts.append(f"🏃 Основная часть: {description}")
                
                # Извлекаем заминку
                if "Заминка:" in description:
                    try:
                        cooldown_text = description.split("Заминка:")[1].strip()
                        description_parts.append(f"🧘 Заминка: {cooldown_text}")
                    except Exception:
                        description_parts.append("🧘 Заминка: Легкий бег 5-10 минут и растяжка")
                else:
                    description_parts.append("🧘 Заминка: Легкий бег 5-10 минут и растяжка")
                
            # 3. Если нет структуры, создаем базовую
            else:
                description_parts = [
                    f"🔄 Разминка: Легкий бег в комфортном темпе 10-15 минут",
                    f"🏃 Основная часть: {description if description else 'Бег в указанном темпе и на указанную дистанцию'}",
                    f"🧘 Заминка: Легкий бег 5-10 минут и растяжка"
                ]
                
            # Объединяем части описания
            structured_description = "\n\n".join(description_parts)
            
            # Добавляем цель тренировки с эмодзи, если указана
            if purpose:
                structured_description += f"\n\n🎯 Цель: {purpose}"
            
            # Добавляем рекомендации по питанию, если указаны
            if nutrition:
                structured_description += f"\n\n🍎 Питание: {nutrition}"
            
            # Добавляем рекомендации по восстановлению, если указаны
            if recovery:
                structured_description += f"\n\n🔋 Восстановление: {recovery}"
                
            # Добавляем дополнительные заметки, если указаны
            if notes:
                structured_description += f"\n\n📝 Примечания: {notes}"
                
        except Exception as e:
            logging.exception(f"Ошибка при создании структурированного описания: {e}")
            structured_description = "🏃 Тренировка в комфортном темпе. Не забудьте о разминке и заминке."
        
        # Формируем итоговое сообщение
        try:
            formatted_message = (
                f"*День {training_day_num}: {day_name} ({day_date})*\n"
                f"Тип: {training_type}\n"
                f"Дистанция: {distance}\n"
                f"Темп: {pace}{heart_rate_text}\n\n"
                f"{structured_description}"
            )
            return formatted_message
            
        except Exception as e:
            logging.exception(f"Ошибка при формировании итогового сообщения: {e}")
            formatted_message = (
                f"*День {training_day_num}*\n"
                f"Тип: {training_type}\n"
                f"Дистанция: {distance}\n\n"
                f"{structured_description}"
            )
            return formatted_message
            
    except Exception as e:
        logging.exception(f"Критическая ошибка в format_training_day: {e}")
        # В случае непредвиденной ошибки возвращаем стандартное сообщение
        return (
            f"*День {training_day_num}*\n"
            f"Тип: Легкая пробежка\n"
            f"Дистанция: 5 км\n"
            f"Темп: 6:00-6:30 мин/км\n\n"
            f"🔄 Разминка: Легкий бег 10-15 минут\n\n"
            f"🏃 Основная часть: Легкая восстановительная пробежка в комфортном темпе\n\n"
            f"🧘 Заминка: Легкий бег 5 минут и растяжка"
        )
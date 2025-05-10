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
                f"*ДЕНЬ {training_day_num}: ЛЕГКАЯ ПРОБЕЖКА (5 км)*\n"
                f"Задачи: восстановление и поддержание базовой выносливости\n\n"
                f"Структура тренировки:\n\n"
                f"1. Разминка (1 км):\n"
                f"• 10-15 минут легкого бега (темп 6:00-6:30 мин/км)\n"
                f"• 5-6 динамических упражнений\n\n"
                f"2. Основная часть (3 км):\n"
                f"• Бег в комфортном темпе 6:00-6:30 мин/км\n"
                f"• Контролируйте дыхание и технику\n\n"
                f"3. Заминка (1 км):\n"
                f"• 5-10 минут очень легкого бега (темп 6:30+ мин/км)\n"
                f"• Короткая растяжка основных мышечных групп\n\n"
                f"Физиологическая цель: Эта тренировка направлена на активное восстановление и поддержание базовой выносливости без создания дополнительного стресса для организма.\n\n"
                f"Советы по выполнению:\n"
                f"• Бегите в максимально комфортном темпе\n"
                f"• Следите за самочувствием\n"
                f"• Не превышайте рекомендуемый темп\n"
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
            
            # Определяем цель тренировки из описания, если не указана явно
            if not purpose and description:
                if "цель" in description.lower():
                    purpose_part = description.lower().split("цель")[1].strip()
                    if "." in purpose_part:
                        purpose = purpose_part.split(".")[0].strip("- :")
                    else:
                        purpose = purpose_part.strip("- :")
            
        except Exception as e:
            logging.exception(f"Ошибка при извлечении базовых данных: {e}")
            return (
                f"*ДЕНЬ {training_day_num}: ЛЕГКАЯ ПРОБЕЖКА (5 км)*\n"
                f"Задачи: восстановление и поддержание базовой выносливости\n\n"
                f"Структура тренировки:\n\n"
                f"1. Разминка (1 км):\n"
                f"• 10-15 минут легкого бега (темп 6:00-6:30 мин/км)\n"
                f"• 5-6 динамических упражнений\n\n"
                f"2. Основная часть (3 км):\n"
                f"• Бег в комфортном темпе 6:00-6:30 мин/км\n"
                f"• Контролируйте дыхание и технику\n\n"
                f"3. Заминка (1 км):\n"
                f"• 5-10 минут очень легкого бега (темп 6:30+ мин/км)\n"
                f"• Короткая растяжка основных мышечных групп\n\n"
                f"Физиологическая цель: Эта тренировка направлена на активное восстановление и поддержание базовой выносливости без создания дополнительного стресса для организма."
            )
        
        # Формируем структурированное описание тренировки
        try:
            # Получаем информацию о размере каждой части тренировки
            # По умолчанию используем примерное распределение
            distance_value = None
            try:
                if isinstance(distance, str) and "км" in distance:
                    distance_value = float(distance.replace("км", "").strip())
                elif isinstance(distance, (int, float)):
                    distance_value = float(distance)
            except (ValueError, TypeError):
                distance_value = None
                
            warmup_distance = "1 км" if distance_value and distance_value > 3 else "0.5 км"
            main_distance = f"{distance_value - 2 if distance_value and distance_value > 3 else distance_value - 1 if distance_value else ''} км"
            cooldown_distance = "1 км" if distance_value and distance_value > 3 else "0.5 км"
            
            # Базовая структура тренировки
            if not purpose and "цель" in description.lower():
                purpose_match = description.lower().split("цель")[1].split(".")[0] if "." in description.lower().split("цель")[1] else description.lower().split("цель")[1]
                purpose = purpose_match.strip("- :")
            
            # Стандартная структура для заголовка тренировки
            title = f"*{day_name.upper()}: {training_type.upper()} ({distance})*"
            tasks = f"Задачи: {purpose.lower() if purpose else 'развитие выносливости'}"
            
            # Структура и сегменты тренировки
            structure_header = "Структура тренировки:"
            
            # Разминка
            warmup_details = []
            if warmup:
                warmup_details.append(warmup)
            else:
                warmup_details.append(f"10-15 минут легкого бега (темп {pace if 'мин/км' in pace else pace + ' мин/км' if pace else '6:00-6:30 мин/км'})")
                warmup_details.append("5-6 динамических упражнений (высокие колени, захлесты голени, выпады)")
                if "интервал" in training_type.lower() or "интервальная" in training_type.lower():
                    warmup_details.append("2-3 ускорения по 30 секунд (темп около 4:30 мин/км)")
            
            warmup_section = f"1. Разминка ({warmup_distance}):\n"
            warmup_section += "\n".join([f"• {item}" for item in warmup_details])
            
            # Основная часть
            main_details = []
            if main_part:
                main_details.append(main_part)
            elif "интервал" in training_type.lower() or "интервальная" in training_type.lower():
                main_details.append(f"6 интервалов по 800м в темпе {pace.split('-')[0] if '-' in pace else pace}")
                main_details.append(f"Отдых между интервалами: медленный бег 400м (5:45-6:00 мин/км)")
                main_details.append("Важно: поддерживайте ровное усилие на всех интервалах")
            elif "темп" in training_type.lower() or "темповая" in training_type.lower():
                main_details.append(f"Бег в темповом режиме {pace}")
                main_details.append("Поддерживайте стабильный темп на всей дистанции")
                main_details.append("Сосредоточьтесь на ровном дыхании и технике")
            else:
                if description:
                    main_details.append(description)
                else:
                    main_details.append(f"Бег в комфортном темпе {pace}")
                    main_details.append("Контролируйте дыхание и технику")
            
            main_section = f"2. Основная часть ({main_distance}):\n"
            main_section += "\n".join([f"• {item}" for item in main_details])
            
            # Заминка
            cooldown_details = []
            if cooldown:
                cooldown_details.append(cooldown)
            else:
                cooldown_details.append(f"5-10 минут очень легкого бега (темп {float(pace.split('-')[0].replace(':', '.')) + 0.3 if '-' in pace and ':' in pace else '6:30+'} мин/км)")
                cooldown_details.append("Короткая растяжка основных мышечных групп")
            
            cooldown_section = f"3. Заминка ({cooldown_distance}):\n"
            cooldown_section += "\n".join([f"• {item}" for item in cooldown_details])
            
            # Физиологическая цель
            physio_goal = "Физиологическая цель: "
            if "интервал" in training_type.lower():
                physio_goal += "Эта тренировка нацелена на повышение лактатного порога - способности организма эффективно утилизировать лактат при высокой интенсивности. По методике Джека Дэниелса, интервалы 800м с интенсивностью 85-90% от максимума оптимально стимулируют улучшение аэробной мощности и лактатного порога."
            elif "темп" in training_type.lower():
                physio_goal += "Эта тренировка нацелена на развитие выносливости на уровне марафонского темпа. Бег в темповом режиме улучшает экономичность бега и повышает способность поддерживать заданный темп на длительной дистанции."
            elif "длительная" in training_type.lower():
                physio_goal += "Эта тренировка нацелена на развитие аэробной выносливости и адаптацию организма к длительным нагрузкам. Длительный бег в аэробной зоне развивает митохондриальную плотность и капилляризацию мышечных волокон."
            elif "восстановительная" in training_type.lower():
                physio_goal += "Эта тренировка направлена на активное восстановление и поддержание базовой выносливости без создания дополнительного стресса для организма."
            else:
                physio_goal += "Эта тренировка направлена на развитие аэробной выносливости и эффективности бега при низкой и средней интенсивности."
            
            # Советы по выполнению
            tips_header = "Советы по выполнению:"
            tips = []
            
            if "интервал" in training_type.lower():
                tips.append("Выполняйте на ровной поверхности (стадион идеален)")
                tips.append("Контролируйте темп через пульс (не должен превышать 90% от максимума)")
                tips.append("Концентрируйтесь на поддержании техники даже при нарастающей усталости")
                tips.append("Не превышайте рекомендуемый темп в первых интервалах")
            elif "темп" in training_type.lower():
                tips.append("Начинайте в более медленном темпе и постепенно наращивайте")
                tips.append("Поддерживайте ровный темп на всей дистанции")
                tips.append("Следите за пульсом (75-85% от максимума)")
                tips.append("Фокусируйтесь на эффективной технике бега")
            elif "длительная" in training_type.lower():
                tips.append("Бегите в разговорном темпе (должны иметь возможность поддерживать разговор)")
                tips.append("Обеспечьте достаточную гидратацию до, во время и после пробежки")
                tips.append("При необходимости делайте короткие паузы для питья")
                tips.append("После тренировки уделите время полноценному восстановлению")
            else:
                tips.append("Бегите в максимально комфортном темпе")
                tips.append("Следите за самочувствием")
                tips.append("Не превышайте рекомендуемый темп")
            
            tips_section = tips_header + "\n" + "\n".join([f"• {tip}" for tip in tips])
            
            # Собираем все в одно сообщение
            sections = [
                title,
                tasks,
                "",
                structure_header,
                "",
                warmup_section,
                "",
                main_section,
                "",
                cooldown_section,
                "",
                physio_goal
            ]
            
            if nutrition:
                sections.append("")
                sections.append(f"Питание: {nutrition}")
            
            if recovery:
                sections.append("")
                sections.append(f"Восстановление: {recovery}")
            
            if heart_rate:
                sections.append("")
                sections.append(f"Пульсовые зоны: {heart_rate}")
            
            # Добавляем советы в конце
            sections.append("")
            sections.append(tips_section)
            
            return "\n".join(sections)
            
        except Exception as e:
            logging.exception(f"Ошибка при создании структурированного описания: {e}")
            return (
                f"*{day_name.upper()}: {training_type.upper()} ({distance})*\n"
                f"Задачи: развитие выносливости\n\n"
                f"Структура тренировки:\n\n"
                f"1. Разминка (1 км):\n"
                f"• 10-15 минут легкого бега (темп 6:00-6:30 мин/км)\n\n"
                f"2. Основная часть ({distance}):\n"
                f"• {description}\n"
                f"• Темп: {pace}\n\n"
                f"3. Заминка (1 км):\n"
                f"• 5-10 минут очень легкого бега\n"
                f"• Короткая растяжка\n\n"
                f"Физиологическая цель: Развитие общей выносливости и эффективности бега."
            )            
    except Exception as e:
        logging.exception(f"Критическая ошибка в format_training_day: {e}")
        # В случае непредвиденной ошибки возвращаем стандартное сообщение
        return (
            f"*ДЕНЬ {training_day_num}: ТРЕНИРОВКА*\n"
            f"Задачи: развитие выносливости\n\n"
            f"Структура тренировки:\n\n"
            f"1. Разминка:\n"
            f"• 10-15 минут легкого бега\n\n"
            f"2. Основная часть:\n"
            f"• Бег в указанном темпе\n\n"
            f"3. Заминка:\n"
            f"• 5-10 минут легкого бега\n"
            f"• Растяжка основных мышечных групп\n\n"
            f"Физиологическая цель: Развитие общей выносливости."
        )
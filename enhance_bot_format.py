#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для добавления улучшенного форматирования тренировок в бота.
Создает новый файл enhanced_bot.py с измененным форматированием.
"""

import os
import sys
import re

def enhance_bot_formatting():
    """
    Читает файл bot.py, заменяет форматирование тренировок на улучшенное,
    и сохраняет результат в enhanced_bot.py.
    """
    # Путь к файлам
    original_file = 'bot.py'
    enhanced_file = 'enhanced_bot.py'
    
    # Убедимся, что файлы существуют
    if not os.path.exists(original_file):
        print(f"Ошибка: {original_file} не найден")
        return False
    
    # Открываем файл
    with open(original_file, 'r') as file:
        content = file.read()
    
    # Паттерн для поиска блока с формированием day_message
    pattern = r'(\s+has_pending_trainings = True\s+)(\s+day_message = \(\s+f"\*День {training_day_num}: {day\[\'day\'\]} \({day\[\'date\'\]}\)\*\\n"\s+f"Тип: {day\[\'training_type\'\]}\\n"\s+f"Дистанция: {day\[\'distance\'\]}\\n"\s+f"Темп: {day\[\'pace\'\]}\\n\\n"\s+f"{day\[\'description\'\]}"\s+\))'
    
    # Замена на улучшенный формат
    replacement = r'''\1
            # Улучшенное форматирование дня тренировки
            day_message = (
                f"*ДЕНЬ {training_day_num}: {day['day'].upper()} ({day['date']})*\\n"
                f"*{day['training_type'].upper()} ({day['distance']})*\\n"
                f"Темп: {day['pace']}\\n\\n"
                f"*Структура тренировки:*\\n\\n"
                f"1. Разминка (1 км):\\n"
                f"• 10-15 минут легкого бега\\n"
                f"• Динамическая растяжка\\n\\n"
                f"2. Основная часть:\\n"
                f"• {day['description']}\\n\\n"
                f"3. Заминка (1 км):\\n"
                f"• 5-10 минут легкого бега\\n"
                f"• Растяжка основных мышечных групп\\n\\n"
                f"*Физиологическая цель:* Эта тренировка направлена на развитие аэробной выносливости и эффективности бега."
            )'''
    
    # Заменяем все вхождения
    updated_content = re.sub(pattern, replacement, content)
    
    # Проверяем, была ли выполнена замена
    if updated_content == content:
        print("Предупреждение: форматирование не было изменено. Шаблон не найден.")
        
        # Попробуем другой подход
        pattern = r'(day_message = \(\s+f"\*День {training_day_num}: {day\[\'day\'\]} \({day\[\'date\'\]}\)\*\\n"\s+f"Тип: {day\[\'training_type\'\]}\\n"\s+f"Дистанция: {day\[\'distance\'\]}\\n"\s+f"Темп: {day\[\'pace\'\]}\\n\\n"\s+f"{day\[\'description\'\]}"\s+\))'
        
        replacement = r'''# Улучшенное форматирование дня тренировки
            day_message = (
                f"*ДЕНЬ {training_day_num}: {day['day'].upper()} ({day['date']})*\\n"
                f"*{day['training_type'].upper()} ({day['distance']})*\\n"
                f"Темп: {day['pace']}\\n\\n"
                f"*Структура тренировки:*\\n\\n"
                f"1. Разминка (1 км):\\n"
                f"• 10-15 минут легкого бега\\n"
                f"• Динамическая растяжка\\n\\n"
                f"2. Основная часть:\\n"
                f"• {day['description']}\\n\\n"
                f"3. Заминка (1 км):\\n"
                f"• 5-10 минут легкого бега\\n"
                f"• Растяжка основных мышечных групп\\n\\n"
                f"*Физиологическая цель:* Эта тренировка направлена на развитие аэробной выносливости и эффективности бега."
            )'''
        
        updated_content = re.sub(pattern, replacement, content)
        
        if updated_content == content:
            print("Предупреждение: не удалось изменить форматирование даже с упрощенным шаблоном.")
            return False
    
    # Записываем изменения в файл enhanced_bot.py
    with open(enhanced_file, 'w') as file:
        file.write(updated_content)
    
    print(f"Улучшенное форматирование тренировок успешно добавлено в {enhanced_file}")
    return True

def manually_update_bot():
    """
    Вручную обновляет файл enhanced_bot.py, если автоматические методы не работают.
    """
    # Ищем и заменяем все вхождения строки форматирования вручную
    with open('enhanced_bot.py', 'r') as file:
        content = file.readlines()
    
    in_day_message_block = False
    day_message_start = -1
    day_message_end = -1
    
    # Ищем блок day_message
    for i, line in enumerate(content):
        if 'day_message = (' in line:
            in_day_message_block = True
            day_message_start = i
            continue
        
        if in_day_message_block and ')' in line and line.strip() == ')':
            day_message_end = i
            break
    
    # Если нашли блок, заменяем его
    if day_message_start > 0 and day_message_end > day_message_start:
        # Новый формат
        new_format = [
            '            # Улучшенное форматирование дня тренировки\n',
            '            day_message = (\n',
            '                f"*ДЕНЬ {training_day_num}: {day[\'day\'].upper()} ({day[\'date\']})*\\n"\n',
            '                f"*{day[\'training_type\'].upper()} ({day[\'distance\']})*\\n"\n',
            '                f"Темп: {day[\'pace\']}\\n\\n"\n',
            '                f"*Структура тренировки:*\\n\\n"\n',
            '                f"1. Разминка (1 км):\\n"\n',
            '                f"• 10-15 минут легкого бега\\n"\n',
            '                f"• Динамическая растяжка\\n\\n"\n',
            '                f"2. Основная часть:\\n"\n',
            '                f"• {day[\'description\']}\\n\\n"\n',
            '                f"3. Заминка (1 км):\\n"\n',
            '                f"• 5-10 минут легкого бега\\n"\n',
            '                f"• Растяжка основных мышечных групп\\n\\n"\n',
            '                f"*Физиологическая цель:* Эта тренировка направлена на развитие аэробной выносливости и эффективности бега."\n',
            '            )\n'
        ]
        
        # Заменяем блок
        content[day_message_start:day_message_end+1] = new_format
        
        # Записываем изменения
        with open('enhanced_bot.py', 'w') as file:
            file.writelines(content)
        
        print("Улучшенное форматирование тренировок успешно добавлено вручную")
        return True
    else:
        print("Не удалось найти блок day_message для замены")
        return False

def create_run_enhanced_bot():
    """
    Создает скрипт для запуска улучшенного бота.
    """
    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота с улучшенным форматированием тренировок.
"""

import asyncio
import logging
from telegram.ext import ApplicationBuilder

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from config import TELEGRAM_TOKEN

# Импортируем улучшенный модуль бота
import enhanced_bot as bot

async def main():
    """Основная функция для запуска бота."""
    try:
        logger.info("Запуск бота с улучшенным форматированием тренировок")
        
        # Настраиваем бота
        application = bot.setup_bot()
        
        # Запускаем бота
        await application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
'''
    
    # Записываем скрипт
    with open('run_enhanced_bot.py', 'w') as file:
        file.write(script_content)
    
    # Делаем файл исполняемым
    os.chmod('run_enhanced_bot.py', 0o755)
    
    print("Скрипт для запуска улучшенного бота успешно создан: run_enhanced_bot.py")
    return True

if __name__ == "__main__":
    print("Добавление улучшенного форматирования тренировок в бота...")
    
    success = enhance_bot_formatting()
    
    if not success:
        print("Автоматическое обновление не удалось, пробую ручной метод...")
        success = manually_update_bot()
    
    if success:
        create_run_enhanced_bot()
        print("\nГотово! Теперь вы можете запустить бота с улучшенным форматированием командой:")
        print("    python run_enhanced_bot.py")
    else:
        print("\nНе удалось добавить улучшенное форматирование.")
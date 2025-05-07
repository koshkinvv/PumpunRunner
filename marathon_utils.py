"""
Утилиты для работы с данными о марафонах.
"""
import csv
import os
from typing import List, Dict

def get_marathons_list() -> List[Dict[str, str]]:
    """
    Читает файл с данными о марафонах и возвращает список словарей с информацией.
    
    Returns:
        List[Dict[str, str]]: Список марафонов с полями: Название, Дата, Место, Тип, Сайт
    """
    marathons = []
    csv_path = os.path.join('data', 'marathons.csv')
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                marathons.append(row)
        return marathons
    except Exception as e:
        print(f"Ошибка при чтении файла марафонов: {e}")
        return []

def format_marathon_info(marathon: Dict[str, str]) -> str:
    """
    Форматирует информацию о марафоне для отображения пользователю.
    
    Args:
        marathon: Словарь с информацией о марафоне
        
    Returns:
        str: Отформатированная строка с информацией
    """
    return (f"🏃 *{marathon['Название']}*\n"
            f"📅 Дата: {marathon['Дата']}\n"
            f"📍 Место: {marathon['Место']}\n"
            f"🏁 Тип: {marathon['Тип']}\n"
            f"🌐 [Сайт мероприятия]({marathon['Сайт']})")

def get_marathon_message_text() -> str:
    """
    Формирует текст сообщения со списком марафонов.
    
    Returns:
        str: Текст сообщения с информацией о марафонах
    """
    marathons = get_marathons_list()
    if not marathons:
        return "К сожалению, информация о марафонах недоступна."
    
    message = "📅 *Ближайшие марафоны*\n\n"
    message += "Вот список ближайших марафонов, которые могут вас заинтересовать:\n\n"
    
    for i, marathon in enumerate(marathons[:5], 1):  # Показываем первые 5 марафонов
        message += f"{i}. {format_marathon_info(marathon)}\n\n"
    
    message += "Вы можете выбрать один из этих марафонов или указать свою дату позже."
    
    return message
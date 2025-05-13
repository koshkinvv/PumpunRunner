"""
Модуль интеграции лендинга с Telegram-ботом.
Обрабатывает верификацию профилей пользователей из лендинга при входе в Telegram-бот.
"""

import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

from db_manager import DBManager


class LandingIntegration:
    """
    Класс для интеграции между лендингом и Telegram-ботом.
    Обеспечивает верификацию профилей, созданных на веб-странице.
    """
    
    @staticmethod
    def check_profile_exists_by_username(username: str) -> bool:
        """
        Проверяет, существует ли профиль для указанного username Telegram.
        
        Args:
            username: Имя пользователя Telegram (без @)
            
        Returns:
            True если профиль существует, False в противном случае
        """
        return DBManager.check_profile_exists_by_username(username)
    
    @staticmethod
    def link_profile_to_telegram_id(username: str, telegram_id: int) -> bool:
        """
        Связывает существующий профиль с Telegram ID пользователя.
        
        Args:
            username: Имя пользователя Telegram (без @)
            telegram_id: ID пользователя в Telegram
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        return DBManager.link_profile_to_telegram_id(username, telegram_id)
    
    @staticmethod
    def get_profile_by_username(username: str) -> Optional[Dict[str, Any]]:
        """
        Получает профиль пользователя по имени пользователя Telegram.
        
        Args:
            username: Имя пользователя Telegram (без @)
            
        Returns:
            Словарь с данными профиля или None, если профиль не найден
        """
        return DBManager.get_profile_by_username(username)
    
    @staticmethod
    def format_profile_for_display(profile: Dict[str, Any]) -> str:
        """
        Форматирует профиль для отображения пользователю в Telegram.
        
        Args:
            profile: Словарь с данными профиля
            
        Returns:
            Отформатированная строка с информацией о профиле
        """
        try:
            # Форматируем информацию о профиле для отображения
            profile_info = (
                f"*Ваш профиль с сайта:*\n\n"
                f"📊 *Основная информация:*\n"
                f"• Дистанция: {profile.get('distance', 'Не указано')}\n"
                f"• Дата соревнования: {profile.get('competition_date', 'Не указано')}\n"
                f"• Целевое время: {profile.get('target_time', 'Не указано')}\n\n"
                f"🧬 *Личные данные:*\n"
                f"• Пол: {profile.get('gender', 'Не указано')}\n"
                f"• Возраст: {profile.get('age', 'Не указано')} лет\n"
                f"• Рост: {profile.get('height', 'Не указано')} см\n"
                f"• Вес: {profile.get('weight', 'Не указано')} кг\n\n"
                f"🏃 *Беговой опыт:*\n"
                f"• Уровень: {profile.get('fitness_level', 'Не указано')}\n"
                f"• Недельный объем: {profile.get('weekly_volume', 'Не указано')} км\n"
                f"• Комфортный темп: {profile.get('comfortable_pace', 'Не указано')}\n\n"
                f"📅 *Расписание:*\n"
                f"• Дни тренировок: {profile.get('preferred_training_days', 'Не указано')}\n"
                f"• Дата начала: {profile.get('training_start_date', 'Не указано')}\n"
            )
            
            return profile_info
        except Exception as e:
            logging.error(f"Ошибка при форматировании профиля: {e}")
            return "Ошибка при отображении профиля."
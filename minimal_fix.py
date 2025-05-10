#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Минимальное исправление для улучшения форматирования тренировок.
Не требует изменения основного кода бота.
"""

import os
import sys
import logging
from telegram.ext import ApplicationBuilder
import asyncio

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импортируем улучшенную функцию форматирования из вашего модуля
from improved_training_format import format_training_day

# Импортируем оригинальный модуль бота
import bot

# Определяем новую функцию форматирования для внедрения в модуль bot
def enhanced_format_day(day, training_day_num):
    """
    Оболочка для улучшенной функции форматирования дня тренировки.
    Эта функция будет использоваться вместо стандартного форматирования в боте.
    """
    return format_training_day(day, training_day_num)

# Определяем патч для форматирования дней в основном модуле bot
def apply_formatting_patch():
    """
    Применяем патч для улучшения форматирования тренировок.
    Монкипатчим необходимые функции бота для использования улучшенного форматирования.
    """
    logger.info("Применяю патч для улучшения форматирования тренировок")
    
    # Сохраняем оригинальную функцию для вывода дней тренировок
    original_callback_handler = bot.callback_query_handler
    original_pending_handler = bot.pending_trainings_command
    
    # Определяем новую функцию вывода тренировок в callback_handler
    async def patched_callback_handler(update, context):
        # Получаем данные из callback_data
        query = update.callback_query
        callback_data = query.data
        
        # Для просмотра плана тренировок, используем улучшенный формат
        if callback_data.startswith("view_plan_"):
            await query.answer()
            plan_id = int(callback_data.split("_")[2])
            
            # Получаем пользователя из базы данных
            telegram_id = query.from_user.id
            db_user_id = bot.DBManager.get_user_id(telegram_id)
            
            if not db_user_id:
                await query.message.reply_text("❌ Ошибка: пользователь не найден в базе данных.")
                return
            
            # Получаем план тренировок
            plan = bot.TrainingPlanManager.get_training_plan(db_user_id, plan_id)
            
            if not plan:
                await query.message.reply_text("❌ Ошибка: план тренировок не найден.")
                return
            
            # Отправляем описание плана
            await query.message.reply_text(
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )
            
            # Получаем выполненные и отмененные тренировки
            completed_days = bot.TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = bot.TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            processed_days = completed_days + canceled_days
            
            # Выводим дни тренировок с улучшенным форматированием
            for idx, day in enumerate(plan['plan_data']['training_days']):
                training_day_num = idx + 1
                
                # Определяем статус тренировки
                status_prefix = ""
                if training_day_num in completed_days:
                    status_prefix = "✅ "
                elif training_day_num in canceled_days:
                    status_prefix = "❌ "
                
                # Используем улучшенное форматирование
                day_message = f"{status_prefix}{enhanced_format_day(day, training_day_num)}"
                
                # Добавляем кнопки только для незавершенных тренировок
                if training_day_num not in processed_days:
                    keyboard = bot.InlineKeyboardMarkup([
                        [
                            bot.InlineKeyboardButton("✅ Отметить как выполненное", 
                                                 callback_data=f"complete_{plan_id}_{training_day_num}"),
                            bot.InlineKeyboardButton("❌ Отменить", 
                                                 callback_data=f"cancel_{plan_id}_{training_day_num}")
                        ]
                    ])
                    await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
                else:
                    await query.message.reply_text(day_message, parse_mode='Markdown')
            
            return
        
        # Для остальных типов callback, используем оригинальный обработчик
        return await original_callback_handler(update, context)
    
    # Патчим оригинальную функцию
    bot.callback_query_handler = patched_callback_handler
    
    # Определяем новую функцию для команды /pending
    async def patched_pending_handler(update, context):
        # Получаем пользователя из базы данных
        telegram_id = update.message.from_user.id
        db_user_id = bot.DBManager.get_user_id(telegram_id)
        
        if not db_user_id:
            await update.message.reply_text("❌ Ошибка: пользователь не найден в базе данных.")
            return
        
        # Получаем текущий план пользователя
        current_plan = bot.DBManager.get_current_plan(db_user_id)
        
        if not current_plan:
            await update.message.reply_text(
                "У вас еще нет активного плана тренировок. Используйте /plan, чтобы создать."
            )
            return
        
        # Получаем план тренировок
        plan_id = current_plan['id']
        plan = bot.TrainingPlanManager.get_training_plan(db_user_id, plan_id)
        
        if not plan:
            await update.message.reply_text("❌ Ошибка: план тренировок не найден.")
            return
        
        # Получаем выполненные и отмененные тренировки
        completed_days = bot.TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = bot.TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
        
        # Фильтруем только незавершенные тренировки
        pending_days = []
        for idx, day in enumerate(plan['plan_data']['training_days']):
            training_day_num = idx + 1
            if training_day_num not in processed_days:
                pending_days.append((training_day_num, day))
        
        if not pending_days:
            # Если нет незавершенных тренировок
            total_days = len(plan['plan_data']['training_days'])
            await update.message.reply_text(
                f"🎉 Все запланированные тренировки выполнены или отменены!\n\n"
                f"✅ Выполнено: {len(completed_days)} из {total_days}\n"
                f"❌ Отменено: {len(canceled_days)} из {total_days}\n\n"
                f"Вы можете создать новый план тренировок через /plan."
            )
            return
        
        # Показываем только 3 ближайшие тренировки для компактности
        pending_to_show = pending_days[:3]
        
        for training_day_num, day in pending_to_show:
            # Используем улучшенное форматирование
            day_message = enhanced_format_day(day, training_day_num)
            
            # Добавляем кнопки для отметки выполнения
            keyboard = bot.InlineKeyboardMarkup([
                [
                    bot.InlineKeyboardButton("✅ Отметить как выполненное", 
                                         callback_data=f"complete_{plan_id}_{training_day_num}"),
                    bot.InlineKeyboardButton("❌ Отменить", 
                                         callback_data=f"cancel_{plan_id}_{training_day_num}")
                ]
            ])
            
            await update.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)
        
        # Показываем статистику
        total_days = len(plan['plan_data']['training_days'])
        remaining_days = len(pending_days)
        
        stats_text = (
            f"📊 *Статистика плана:*\n"
            f"✅ Выполнено: {len(completed_days)} из {total_days}\n"
            f"❌ Отменено: {len(canceled_days)} из {total_days}\n"
            f"⏳ Осталось: {remaining_days} из {total_days}"
        )
        
        if remaining_days > 3:
            stats_text += f"\n\nПоказаны первые 3 из {remaining_days} оставшихся тренировок."
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    # Патчим оригинальную функцию
    bot.pending_trainings_command = patched_pending_handler
    
    logger.info("Патч для улучшения форматирования тренировок успешно применен")

async def main():
    """Основная функция для запуска бота с улучшенным форматированием."""
    try:
        # Применяем патч для улучшения форматирования
        apply_formatting_patch()
        
        # Запускаем стандартную настройку бота
        application = bot.setup_bot()
        
        # Запускаем бота
        logger.info("Запускаю бот с улучшенным форматированием тренировок")
        await application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)

# Запуск бота
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        sys.exit(1)
import os
import json
import io
from datetime import datetime, timedelta
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
# Определяем константу ConversationHandler.END
END = ConversationHandler.END
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from config import TELEGRAM_TOKEN, logging, STATES
from models import create_tables
from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from openai_service import OpenAIService
from conversation import RunnerProfileConversation
from image_analyzer import ImageAnalyzer

# Импортируем улучшенную функцию форматирования тренировок
from improved_training_format import format_training_day as improved_format_training_day

# Используем улучшенную версию для форматирования тренировок
def format_training_day(day, training_day_num):
    """
    Обертка для улучшенной функции форматирования тренировок.
    Использует новую реализацию из модуля improved_training_format.
    
    Args:
        day: Словарь с данными о дне тренировки
        training_day_num: Номер дня тренировки
        
    Returns:
        str: Отформатированное сообщение о дне тренировки
    """
    return improved_format_training_day(day, training_day_num)


def format_weekly_volume(volume, default_value="0"):
    """
    Форматирует значение еженедельного объема бега, избегая отображения None.
    
    Args:
        volume: Текущее значение объема
        default_value: Значение по умолчанию, если текущее значение None или "None"
        
    Returns:
        Отформатированная строка с объемом бега
    """
    # Если volume равен None или строке "None", используем значение по умолчанию
    if volume is None or volume == "None":
        return f"{default_value} км/неделю"
    
    # Если volume уже содержит единицу измерения, возвращаем как есть
    if isinstance(volume, str) and "км" in volume:
        return volume
    
    # Иначе добавляем единицу измерения
    return f"{volume} км/неделю"


async def send_main_menu(update, context, message_text="Что вы хотите сделать?"):
    """Отправляет главное меню с кнопками."""
    # Создаем кнопки в стиле ReplyKeyboardMarkup как на скриншоте
    keyboard = ReplyKeyboardMarkup([
        ["📋 Мой план", "📊 Моя статистика"],
        ["👟 Отметить тренировку", "ℹ️ Помощь"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(message_text, reply_markup=keyboard)


async def help_command(update, context):
    """Handler for the /help command."""
    help_text = """
*RunTracker Bot - Ваш персональный беговой тренер*

Бот поможет вам создать персонализированный план тренировок и отслеживать прогресс.

*Основные команды:*
/plan - Создать или просмотреть план тренировок
/pending - Показать предстоящие тренировки
/update - Обновить свой профиль
/help - Показать это сообщение

*Как пользоваться ботом:*
1. Заполните свой профиль бегуна
2. Сгенерируйте план тренировок
3. Отмечайте выполненные тренировки
4. Отслеживайте свой прогресс

*Для любых вопросов пишите @run_coach_support*
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def pending_trainings_command(update, context):
    """Handler for the /pending command - shows only pending (not completed) trainings."""
    user_id = update.message.from_user.id
    db_manager = DBManager()
    
    # Получаем текущий план пользователя
    current_plan = db_manager.get_current_plan(user_id)
    
    if not current_plan:
        await update.message.reply_text(
            "У вас еще нет активного плана тренировок. Используйте /plan, чтобы создать новый план."
        )
        return
    
    # Получаем все тренировки из плана
    training_manager = TrainingPlanManager(user_id)
    plan_data = training_manager.get_training_plan(current_plan['id'])
    
    if not plan_data or 'plan_data' not in plan_data or 'training_days' not in plan_data['plan_data']:
        await update.message.reply_text(
            "❌ Ошибка в структуре плана тренировок. Пожалуйста, создайте новый план через /plan."
        )
        return
    
    # Фильтруем только невыполненные (не отмеченные как completed или canceled) тренировки
    pending_days = []
    completed_days = []
    canceled_days = []
    
    for i, day in enumerate(plan_data['plan_data']['training_days'], 1):
        # Проверяем статус тренировки
        status = training_manager.get_training_status(current_plan['id'], i)
        
        if status == 'completed':
            completed_days.append((i, day))
        elif status == 'canceled':
            canceled_days.append((i, day))
        else:
            pending_days.append((i, day))
    
    # Если нет ожидающих тренировок, показываем сообщение
    if not pending_days:
        # Все тренировки выполнены или отменены
        if completed_days or canceled_days:
            message = f"🎉 *План тренировок завершен!*\n\n"
            message += f"✅ Выполнено: {len(completed_days)} тренировок\n"
            message += f"❌ Отменено: {len(canceled_days)} тренировок\n\n"
            message += "Вы можете создать новый план тренировок через /plan или продолжить с текущим планом."
            
            # Добавляем кнопку для продолжения тренировок
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{current_plan['id']}")]
            ])
            
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "У вас еще нет активного плана тренировок. Используйте /plan, чтобы создать новый план."
            )
        return
    
    # Показываем только ближайшие 3 тренировки для компактности
    pending_to_show = pending_days[:3]
    
    message = f"*Ближайшие запланированные тренировки:*\n\n"
    
    for i, day in pending_to_show:
        # Форматируем день тренировки
        day_info = format_training_day(day, i)
        message += f"{day_info}\n\n"
        
        # Добавляем кнопки для отметки выполнения под каждой тренировкой
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Выполнено", callback_data=f"complete_training_{current_plan['id']}_{i}"),
                InlineKeyboardButton("❌ Пропущено", callback_data=f"cancel_training_{current_plan['id']}_{i}")
            ]
        ])
        
        # Отправляем сообщение с кнопками
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        
        # Сбрасываем сообщение для следующей тренировки
        message = ""
    
    # Показываем общую статистику
    total_count = len(plan_data['plan_data']['training_days'])
    completed_count = len(completed_days)
    canceled_count = len(canceled_days)
    pending_count = len(pending_days)
    
    stats_message = f"*Статистика плана:*\n"
    stats_message += f"✅ Выполнено: {completed_count} из {total_count}\n"
    stats_message += f"❌ Пропущено: {canceled_count} из {total_count}\n"
    stats_message += f"⏳ Осталось: {pending_count} из {total_count}\n"
    
    if pending_count > 3:
        stats_message += f"\nПоказаны {len(pending_to_show)} из {pending_count} предстоящих тренировок."
    
    await update.message.reply_text(stats_message, parse_mode='Markdown')


async def generate_plan_command(update, context):
    """Handler for the /plan command."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # Проверяем, есть ли профиль бегуна у пользователя
    db_manager = DBManager()
    runner_profile = db_manager.get_runner_profile(user_id)
    
    if not runner_profile:
        # Если профиля нет, предлагаем его создать
        message = "Для создания плана тренировок сначала нужно заполнить свой профиль бегуна."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Создать профиль", callback_data="create_profile")]
        ])
        await update.message.reply_text(message, reply_markup=keyboard)
        return
    
    # Проверяем, есть ли уже план тренировок
    current_plan = db_manager.get_current_plan(user_id)
    
    if current_plan:
        # Если план уже есть, показываем его и предлагаем создать новый
        message = f"У вас уже есть план тренировок: *{current_plan['plan_name']}*"
        
        # Получаем данные плана для просмотра
        training_manager = TrainingPlanManager(user_id)
        plan_data = training_manager.get_training_plan(current_plan['id'])
        
        if not plan_data or 'plan_data' not in plan_data or 'training_days' not in plan_data['plan_data']:
            message += "\n\n❌ Ошибка в структуре плана. Рекомендуется создать новый план."
        else:
            # Добавляем краткую информацию о плане
            total_trainings = len(plan_data['plan_data']['training_days'])
            completed = training_manager.count_completed_trainings(current_plan['id'])
            canceled = training_manager.count_canceled_trainings(current_plan['id'])
            remaining = total_trainings - (completed + canceled)
            
            message += f"\n\n✅ Выполнено: {completed} тренировок"
            message += f"\n❌ Пропущено: {canceled} тренировок"
            message += f"\n⏳ Осталось: {remaining} тренировок"
        
        # Кнопки для просмотра или создания нового плана
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ Просмотреть текущий план", callback_data=f"view_plan_{current_plan['id']}")],
            [InlineKeyboardButton("🆕 Создать новый план", callback_data="new_plan")]
        ])
        
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    # Если профиль есть, но плана нет, генерируем новый план
    await update.message.reply_text("⏳ Генерирую персонализированный план тренировок на основе вашего профиля...")
    
    try:
        # Генерируем план с использованием OpenAI
        openai_service = OpenAIService()
        training_plan = openai_service.generate_training_plan(runner_profile)
        
        if not training_plan:
            await update.message.reply_text(
                "❌ Ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
            )
            return
        
        # Сохраняем план в базу данных
        training_manager = TrainingPlanManager(user_id)
        plan_id = training_manager.save_training_plan(training_plan)
        
        if not plan_id:
            await update.message.reply_text(
                "❌ Ошибка при сохранении плана тренировок. Пожалуйста, попробуйте позже."
            )
            return
        
        # Показываем успешное сообщение и предлагаем просмотреть план
        message = f"✅ План тренировок успешно создан!\n\n*{training_plan['plan_name']}*\n\n{training_plan['plan_description']}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ Просмотреть план", callback_data=f"view_plan_{plan_id}")],
            [InlineKeyboardButton("🏃 Показать ближайшие тренировки", callback_data=f"pending_trainings")]
        ])
        
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        
        # Отправляем сообщение о том, что пользователь может присоединиться к чату с бета-тестерами
        await update.message.reply_text(
            "🔍 Вы участвуете в бета-тестировании RunTracker Bot! Присоединяйтесь к нашему чату с другими бегунами, где вы можете оставить отзыв и задать вопросы: @runtracker_beta"
        )
    
    except Exception as e:
        logging.exception(f"Ошибка при генерации плана: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при создании плана тренировок. Пожалуйста, попробуйте позже или свяжитесь с @run_coach_support."
        )


async def update_profile_command(update, context):
    """Handler for the /update command - starts runner profile update dialog."""
    # Инициализируем обработчик профиля
    profile_handler = RunnerProfileConversation()
    
    # Запускаем обновление профиля
    return await profile_handler.start_update(update, context)


async def callback_query_handler(update, context):
    """Handler for inline button callbacks."""
    query = update.callback_query
    await query.answer()  # Отмечаем, что обработали callback
    
    # Получаем данные из callback_data
    callback_data = query.data
    
    # Обрабатываем различные типы callback_data
    if callback_data == "create_profile":
        # Создание профиля
        profile_handler = RunnerProfileConversation()
        await profile_handler.start(update, context)
        return
    
    elif callback_data == "new_plan":
        # Создание нового плана
        user_id = query.from_user.id
        
        await query.message.reply_text("⏳ Генерирую новый персонализированный план тренировок...")
        
        try:
            # Получаем профиль бегуна
            db_manager = DBManager()
            runner_profile = db_manager.get_runner_profile(user_id)
            
            if not runner_profile:
                await query.message.reply_text(
                    "❌ Не удалось найти ваш профиль бегуна. Пожалуйста, создайте его сначала."
                )
                return
            
            # Генерируем план с использованием OpenAI
            openai_service = OpenAIService()
            training_plan = openai_service.generate_training_plan(runner_profile)
            
            if not training_plan:
                await query.message.reply_text(
                    "❌ Ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
                )
                return
            
            # Сохраняем план в базу данных
            training_manager = TrainingPlanManager(user_id)
            plan_id = training_manager.save_training_plan(training_plan)
            
            if not plan_id:
                await query.message.reply_text(
                    "❌ Ошибка при сохранении плана тренировок. Пожалуйста, попробуйте позже."
                )
                return
            
            # Показываем успешное сообщение и предлагаем просмотреть план
            message = f"✅ Новый план тренировок успешно создан!\n\n*{training_plan['plan_name']}*\n\n{training_plan['plan_description']}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ Просмотреть план", callback_data=f"view_plan_{plan_id}")],
                [InlineKeyboardButton("🏃 Показать ближайшие тренировки", callback_data=f"pending_trainings")]
            ])
            
            await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        
        except Exception as e:
            logging.exception(f"Ошибка при генерации плана: {e}")
            await query.message.reply_text(
                "❌ Произошла ошибка при создании плана тренировок. Пожалуйста, попробуйте позже или свяжитесь с @run_coach_support."
            )
    
    elif callback_data.startswith("view_plan_"):
        # Просмотр плана тренировок
        plan_id = int(callback_data.split("_")[2])
        user_id = query.from_user.id
        
        # Получаем данные плана
        training_manager = TrainingPlanManager(user_id)
        plan_data = training_manager.get_training_plan(plan_id)
        
        if not plan_data or 'plan_data' not in plan_data or 'training_days' not in plan_data['plan_data']:
            await query.message.reply_text(
                "❌ Ошибка в структуре плана тренировок. Пожалуйста, создайте новый план."
            )
            return
        
        # Выводим информацию о плане
        message = f"*{plan_data['plan_name']}*\n\n{plan_data['plan_description']}\n\n"
        
        # Отправляем сообщение с общей информацией о плане
        await query.message.reply_text(message, parse_mode='Markdown')
        
        # Выводим список тренировок
        for i, day in enumerate(plan_data['plan_data']['training_days'], 1):
            # Проверяем статус тренировки
            status = training_manager.get_training_status(plan_id, i)
            status_emoji = ""
            
            if status == 'completed':
                status_emoji = "✅ "
            elif status == 'canceled':
                status_emoji = "❌ "
            
            # Форматируем день тренировки
            day_info = format_training_day(day, i)
            training_message = f"{status_emoji}{day_info}"
            
            # Если тренировка еще не выполнена и не отменена, добавляем кнопки
            if not status:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Выполнено", callback_data=f"complete_training_{plan_id}_{i}"),
                        InlineKeyboardButton("❌ Пропущено", callback_data=f"cancel_training_{plan_id}_{i}")
                    ]
                ])
                
                await query.message.reply_text(training_message, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await query.message.reply_text(training_message, parse_mode='Markdown')
    
    elif callback_data == "pending_trainings":
        # Просмотр предстоящих тренировок
        await pending_trainings_command(update, context)
    
    elif callback_data.startswith("complete_training_"):
        # Отметка тренировки как выполненной
        parts = callback_data.split("_")
        plan_id = int(parts[2])
        training_day = int(parts[3])
        user_id = query.from_user.id
        
        # Отмечаем тренировку как выполненную
        training_manager = TrainingPlanManager(user_id)
        success = training_manager.mark_training_completed(plan_id, training_day)
        
        if success:
            await query.message.reply_text(
                f"✅ Тренировка #{training_day} отмечена как выполненная! Поздравляем!"
            )
            
            # Обновляем информацию о тренировке
            plan_data = training_manager.get_training_plan(plan_id)
            if plan_data and 'plan_data' in plan_data and 'training_days' in plan_data['plan_data']:
                if training_day <= len(plan_data['plan_data']['training_days']):
                    day = plan_data['plan_data']['training_days'][training_day - 1]
                    day_info = format_training_day(day, training_day)
                    
                    # Редактируем сообщение, добавляя статус
                    try:
                        await query.message.edit_text(
                            f"✅ {day_info}",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logging.exception(f"Ошибка при обновлении сообщения: {e}")
            
            # Проверяем, не завершен ли план
            completed = training_manager.count_completed_trainings(plan_id)
            canceled = training_manager.count_canceled_trainings(plan_id)
            total = len(plan_data['plan_data']['training_days'])
            
            if completed + canceled == total:
                # Все тренировки выполнены или отменены, план завершен
                message = f"🎉 *План тренировок завершен!*\n\n"
                message += f"✅ Выполнено: {completed} тренировок\n"
                message += f"❌ Отменено: {canceled} тренировок\n\n"
                message += "Вы можете создать новый план тренировок или продолжить с текущим планом."
                
                # Добавляем кнопку для продолжения тренировок
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                ])
                
                await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await query.message.reply_text(
                "❌ Ошибка при отметке тренировки. Пожалуйста, попробуйте позже."
            )
    
    elif callback_data.startswith("cancel_training_"):
        # Отметка тренировки как отмененной
        parts = callback_data.split("_")
        plan_id = int(parts[2])
        training_day = int(parts[3])
        user_id = query.from_user.id
        
        # Отмечаем тренировку как отмененную
        training_manager = TrainingPlanManager(user_id)
        success = training_manager.mark_training_canceled(plan_id, training_day)
        
        if success:
            await query.message.reply_text(
                f"❌ Тренировка #{training_day} отмечена как пропущенная."
            )
            
            # Обновляем информацию о тренировке
            plan_data = training_manager.get_training_plan(plan_id)
            if plan_data and 'plan_data' in plan_data and 'training_days' in plan_data['plan_data']:
                if training_day <= len(plan_data['plan_data']['training_days']):
                    day = plan_data['plan_data']['training_days'][training_day - 1]
                    day_info = format_training_day(day, training_day)
                    
                    # Редактируем сообщение, добавляя статус
                    try:
                        await query.message.edit_text(
                            f"❌ {day_info}",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logging.exception(f"Ошибка при обновлении сообщения: {e}")
            
            # Проверяем, не завершен ли план
            completed = training_manager.count_completed_trainings(plan_id)
            canceled = training_manager.count_canceled_trainings(plan_id)
            total = len(plan_data['plan_data']['training_days'])
            
            if completed + canceled == total:
                # Все тренировки выполнены или отменены, план завершен
                message = f"🎉 *План тренировок завершен!*\n\n"
                message += f"✅ Выполнено: {completed} тренировок\n"
                message += f"❌ Отменено: {canceled} тренировок\n\n"
                message += "Вы можете создать новый план тренировок или продолжить с текущим планом."
                
                # Добавляем кнопку для продолжения тренировок
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                ])
                
                await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await query.message.reply_text(
                "❌ Ошибка при отметке тренировки. Пожалуйста, попробуйте позже."
            )
    
    elif callback_data.startswith("continue_plan_"):
        # Продолжение тренировок с текущим планом
        plan_id = int(callback_data.split("_")[2])
        user_id = query.from_user.id
        
        # Получаем профиль бегуна
        db_manager = DBManager()
        runner_profile = db_manager.get_runner_profile(user_id)
        
        await query.message.reply_text("⏳ Генерирую продолжение плана тренировок...")
        
        try:
            # Получаем текущий план
            training_manager = TrainingPlanManager(user_id)
            current_plan = training_manager.get_training_plan(plan_id)
            
            if not current_plan or 'plan_data' not in current_plan or 'training_days' not in current_plan['plan_data']:
                await query.message.reply_text(
                    "❌ Ошибка в структуре текущего плана тренировок. Пожалуйста, создайте новый план."
                )
                return
            
            # Генерируем продолжение плана с использованием OpenAI
            openai_service = OpenAIService()
            
            # Передаем информацию о текущем плане для продолжения
            runner_profile['current_plan'] = current_plan
            training_plan = openai_service.generate_training_plan(runner_profile, continue_plan=True)
            
            if not training_plan:
                await query.message.reply_text(
                    "❌ Ошибка при генерации продолжения плана. Пожалуйста, попробуйте позже."
                )
                return
            
            # Сохраняем новый план в базу данных
            new_plan_id = training_manager.save_training_plan(training_plan)
            
            if not new_plan_id:
                await query.message.reply_text(
                    "❌ Ошибка при сохранении плана тренировок. Пожалуйста, попробуйте позже."
                )
                return
            
            # Показываем успешное сообщение и предлагаем просмотреть план
            message = f"✅ План тренировок успешно продолжен!\n\n*{training_plan['plan_name']}*\n\n{training_plan['plan_description']}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ Просмотреть план", callback_data=f"view_plan_{new_plan_id}")],
                [InlineKeyboardButton("🏃 Показать ближайшие тренировки", callback_data=f"pending_trainings")]
            ])
            
            await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        
        except Exception as e:
            logging.exception(f"Ошибка при генерации продолжения плана: {e}")
            await query.message.reply_text(
                "❌ Произошла ошибка при создании продолжения плана. Пожалуйста, попробуйте позже или свяжитесь с @run_coach_support."
            )
    
    # Другие типы callback_data могут быть добавлены здесь


async def handle_photo(update, context):
    """Handler for photo messages to analyze workout screenshots."""
    user_id = update.message.from_user.id
    
    # Получаем самое большое доступное изображение
    photo_file = await update.message.photo[-1].get_file()
    
    # Скачиваем изображение
    photo_bytes = io.BytesIO()
    await photo_file.download(out=photo_bytes)
    photo_bytes.seek(0)
    
    await update.message.reply_text("🔍 Анализирую изображение...")
    
    try:
        # Анализируем изображение с помощью OpenAI
        image_analyzer = ImageAnalyzer()
        analysis_result = await image_analyzer.analyze_workout_image(photo_bytes.getvalue())
        
        if not analysis_result:
            await update.message.reply_text(
                "❌ Не удалось распознать данные о тренировке на изображении. "
                "Пожалуйста, загрузите более четкий скриншот тренировочного приложения."
            )
            return
        
        # Проверяем, распознан ли тип тренировки
        if 'workout_type' in analysis_result and analysis_result['workout_type'].lower() == 'running':
            # Формируем сообщение с информацией о тренировке
            message = "*Информация о беговой тренировке:*\n\n"
            
            if 'distance' in analysis_result:
                message += f"🏃 Дистанция: {analysis_result['distance']}\n"
            if 'duration' in analysis_result:
                message += f"⏱️ Длительность: {analysis_result['duration']}\n"
            if 'pace' in analysis_result:
                message += f"⚡ Темп: {analysis_result['pace']}\n"
            if 'calories' in analysis_result:
                message += f"🔥 Калории: {analysis_result['calories']}\n"
            if 'date' in analysis_result:
                message += f"📅 Дата: {analysis_result['date']}\n"
            
            # Проверяем, есть ли активный план тренировок
            db_manager = DBManager()
            current_plan = db_manager.get_current_plan(user_id)
            
            # Отправляем сообщение с распознанной информацией
            if current_plan:
                message += "\nХотите отметить тренировку как выполненную в вашем плане?"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненную", callback_data=f"mark_by_image_{current_plan['id']}")]
                ])
                
                await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
        else:
            # Если это не беговая тренировка
            workout_type = analysis_result.get('workout_type', 'Неизвестный тип тренировки')
            await update.message.reply_text(
                f"👍 Распознана тренировка типа: {workout_type}\n\n"
                f"📝 В настоящий момент бот поддерживает только беговые тренировки. "
                f"Поддержка других типов тренировок появится в будущих обновлениях!"
            )
    
    except Exception as e:
        logging.exception(f"Ошибка при анализе изображения: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при анализе изображения. Пожалуйста, попробуйте позже или свяжитесь с @run_coach_support."
        )


def setup_bot(application):
    """Configure and return the bot application."""
    # Основные команды
    application.add_handler(CommandHandler("start", send_main_menu))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CommandHandler("pending", pending_trainings_command))
    application.add_handler(CommandHandler("update", update_profile_command))
    
    # Обработчик для кнопок inline
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Обработчик для фотографий (анализ скриншотов тренировок)
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Обработчик для обновления профиля бегуна
    profile_handler = RunnerProfileConversation()
    application.add_handler(profile_handler.get_conversation_handler())
    
    # Обработчик для текстовых сообщений
    async def text_message_handler(update, context):
        """Обработчик текстовых сообщений от пользователя."""
        text = update.message.text
        
        # Простые ответы на распространенные запросы
        if text.lower() in ["привет", "здравствуй", "hi", "hello"]:
            await update.message.reply_text(f"Привет, {update.message.from_user.first_name}! Чем я могу помочь?")
        elif "помощь" in text.lower() or "help" in text.lower():
            await help_command(update, context)
        elif "план" in text.lower() or "plan" in text.lower():
            await generate_plan_command(update, context)
        elif "тренировк" in text.lower() or "workout" in text.lower():
            await pending_trainings_command(update, context)
        else:
            await update.message.reply_text(
                "Извините, я не понимаю этот запрос. Пожалуйста, используйте команды или кнопки в меню."
            )
    
    # Добавляем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Обработчик для отмены текущего диалога
    async def cancel_command(update, context):
        """Handler for the /cancel command - cancels current conversation."""
        await update.message.reply_text(
            "Действие отменено. Чем я могу помочь?",
            reply_markup=ReplyKeyboardRemove()
        )
        await send_main_menu(update, context)
        return END
    
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    return application
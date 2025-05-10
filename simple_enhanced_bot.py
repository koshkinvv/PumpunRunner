import os
import json
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from config import TELEGRAM_TOKEN, logging
from models import create_tables
from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from openai_service import OpenAIService
from conversation import RunnerProfileConversation

# Импортируем улучшенную функцию форматирования тренировок
from improved_training_format import format_training_day

def format_weekly_volume(volume, default_value="0"):
    """
    Форматирует значение еженедельного объема бега, избегая отображения None.
    
    Args:
        volume: Текущее значение объема
        default_value: Значение по умолчанию, если текущее значение None или "None"
        
    Returns:
        Отформатированная строка с объемом бега
    """
    if volume is None or volume == "None" or not volume:
        return f"{default_value} км/неделю"
    
    # Если в строке уже содержится единица измерения, возвращаем как есть
    if isinstance(volume, str) and ("км/неделю" in volume or "км" in volume):
        return volume
    
    # Иначе добавляем единицу измерения
    return f"{volume} км/неделю"

async def help_command(update, context):
    """Handler for the /help command."""
    help_text = (
        "👋 Привет! Я бот-помощник для бегунов. Вот что я могу:\n\n"
        "/plan - Создать или просмотреть план тренировок\n"
        "/pending - Показать только незавершенные тренировки\n"
        "/help - Показать это сообщение\n\n"
        "Если у вас есть вопросы, обратитесь к @run_coach_support"
    )
    await update.message.reply_text(help_text)

async def pending_trainings_command(update, context):
    """Handler for the /pending command - shows only pending (not completed) trainings."""
    user_id = update.message.from_user.id
    db_manager = DBManager()
    
    # Проверяем, есть ли текущий план
    current_plan = db_manager.get_current_plan(user_id)
    if not current_plan:
        await update.message.reply_text(
            "У вас еще нет активного плана тренировок. Используйте /plan, чтобы создать."
        )
        return
    
    # Получаем план тренировок
    training_manager = TrainingPlanManager(user_id)
    plan_data = training_manager.get_training_plan(current_plan['id'])
    
    if not plan_data or 'plan_data' not in plan_data or 'training_days' not in plan_data['plan_data']:
        await update.message.reply_text(
            "❌ Ошибка в структуре плана тренировок. Создайте новый план через /plan."
        )
        return
    
    # Фильтруем только незавершенные тренировки
    pending_days = []
    completed_count = 0
    canceled_count = 0
    
    for i, day in enumerate(plan_data['plan_data']['training_days'], 1):
        # Проверяем статус тренировки
        status = training_manager.get_training_status(current_plan['id'], i)
        
        if status == 'completed':
            completed_count += 1
        elif status == 'canceled':
            canceled_count += 1
        else:
            pending_days.append((i, day))
    
    if not pending_days:
        # Если нет незавершенных тренировок
        total_days = len(plan_data['plan_data']['training_days'])
        await update.message.reply_text(
            f"🎉 Все запланированные тренировки выполнены или отменены!\n\n"
            f"✅ Выполнено: {completed_count} из {total_days}\n"
            f"❌ Отменено: {canceled_count} из {total_days}\n\n"
            f"Вы можете создать новый план тренировок через /plan."
        )
        return
    
    # Показываем только 3 ближайшие тренировки для компактности
    pending_to_show = pending_days[:3]
    
    for i, day in pending_to_show:
        # Форматируем день тренировки
        formatted_day = format_training_day(day, i)
        
        # Добавляем кнопки для отметки выполнения
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Выполнено", callback_data=f"complete_training_{current_plan['id']}_{i}"),
                InlineKeyboardButton("❌ Пропущено", callback_data=f"cancel_training_{current_plan['id']}_{i}")
            ]
        ])
        
        await update.message.reply_text(formatted_day, reply_markup=keyboard, parse_mode='Markdown')
    
    # Показываем статистику
    total_days = len(plan_data['plan_data']['training_days'])
    remaining_days = len(pending_days)
    
    stats_text = (
        f"📊 *Статистика плана:*\n"
        f"✅ Выполнено: {completed_count} из {total_days}\n"
        f"❌ Отменено: {canceled_count} из {total_days}\n"
        f"⏳ Осталось: {remaining_days} из {total_days}"
    )
    
    if remaining_days > 3:
        stats_text += f"\n\nПоказаны первые 3 из {remaining_days} оставшихся тренировок."
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def generate_plan_command(update, context):
    """Handler for the /plan command."""
    user_id = update.message.from_user.id
    db_manager = DBManager()
    
    # Проверяем, есть ли профиль бегуна
    runner_profile = db_manager.get_runner_profile(user_id)
    if not runner_profile:
        # Если профиля нет, предлагаем его создать
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Создать профиль", callback_data="create_profile")]
        ])
        await update.message.reply_text(
            "Для создания плана тренировок сначала нужно заполнить свой профиль бегуна.",
            reply_markup=keyboard
        )
        return
    
    # Проверяем, есть ли уже план тренировок
    current_plan = db_manager.get_current_plan(user_id)
    if current_plan:
        # Если план уже есть, показываем его и предлагаем создать новый
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Посмотреть текущий план", callback_data=f"view_plan_{current_plan['id']}")],
            [InlineKeyboardButton("Создать новый план", callback_data="new_plan")]
        ])
        await update.message.reply_text(
            f"У вас уже есть план тренировок: {current_plan['plan_name']}.\n"
            f"Вы можете посмотреть его или создать новый.",
            reply_markup=keyboard
        )
        return
    
    # Если профиль есть, но плана нет, генерируем новый план
    await update.message.reply_text("⏳ Генерирую персонализированный план тренировок...")
    
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Посмотреть план", callback_data=f"view_plan_{plan_id}")]
        ])
        
        await update.message.reply_text(
            f"✅ План тренировок успешно создан!\n\n"
            f"{training_plan['plan_name']}\n\n"
            f"{training_plan['plan_description']}",
            reply_markup=keyboard
        )
    
    except Exception as e:
        logging.exception(f"Ошибка при генерации плана: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при создании плана тренировок. Пожалуйста, попробуйте позже."
        )

async def callback_query_handler(update, context):
    """Handler for inline button callbacks."""
    query = update.callback_query
    await query.answer()  # Отмечаем, что обработали callback
    
    # Получаем данные из callback_data
    callback_data = query.data
    
    if callback_data == "create_profile":
        # Создание профиля
        profile_handler = RunnerProfileConversation()
        await profile_handler.start(update, context)
    
    elif callback_data == "new_plan":
        # Создание нового плана
        user_id = query.from_user.id
        
        await query.message.reply_text("⏳ Генерирую новый персонализированный план тренировок...")
        
        try:
            # Получаем профиль бегуна
            db_manager = DBManager()
            runner_profile = db_manager.get_runner_profile(user_id)
            
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
            
            # Показываем успешное сообщение и предлагаем просмотреть план
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Посмотреть план", callback_data=f"view_plan_{plan_id}")]
            ])
            
            await query.message.reply_text(
                f"✅ Новый план тренировок успешно создан!\n\n"
                f"{training_plan['plan_name']}\n\n"
                f"{training_plan['plan_description']}",
                reply_markup=keyboard
            )
        
        except Exception as e:
            logging.exception(f"Ошибка при генерации плана: {e}")
            await query.message.reply_text(
                "❌ Произошла ошибка при создании плана тренировок. Пожалуйста, попробуйте позже."
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
        await query.message.reply_text(
            f"*{plan_data['plan_name']}*\n\n"
            f"{plan_data['plan_description']}",
            parse_mode='Markdown'
        )
        
        # Выводим только первые 3 дня тренировок для компактности
        days_to_show = min(3, len(plan_data['plan_data']['training_days']))
        
        for i in range(days_to_show):
            day_num = i + 1
            day = plan_data['plan_data']['training_days'][i]
            
            # Проверяем статус тренировки
            status = training_manager.get_training_status(plan_id, day_num)
            status_emoji = ""
            
            if status == 'completed':
                status_emoji = "✅ "
            elif status == 'canceled':
                status_emoji = "❌ "
            
            # Форматируем день тренировки с использованием улучшенной функции
            formatted_day = f"{status_emoji}{format_training_day(day, day_num)}"
            
            # Если тренировка еще не выполнена и не отменена, добавляем кнопки
            if not status:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Выполнено", callback_data=f"complete_training_{plan_id}_{day_num}"),
                        InlineKeyboardButton("❌ Пропущено", callback_data=f"cancel_training_{plan_id}_{day_num}")
                    ]
                ])
                
                await query.message.reply_text(formatted_day, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await query.message.reply_text(formatted_day, parse_mode='Markdown')
        
        # Если дней больше 3, сообщаем об этом
        if len(plan_data['plan_data']['training_days']) > 3:
            total_days = len(plan_data['plan_data']['training_days'])
            await query.message.reply_text(
                f"Показаны первые {days_to_show} из {total_days} дней тренировок.\n"
                f"Чтобы увидеть все тренировки, используйте /pending."
            )
    
    elif callback_data.startswith("complete_training_"):
        # Отметка тренировки как выполненной
        parts = callback_data.split("_")
        plan_id = int(parts[2])
        day_num = int(parts[3])
        user_id = query.from_user.id
        
        # Отмечаем тренировку как выполненную
        training_manager = TrainingPlanManager(user_id)
        success = training_manager.mark_training_completed(plan_id, day_num)
        
        if success:
            await query.message.reply_text(f"✅ Тренировка #{day_num} отмечена как выполненная!")
            
            # Обновляем сообщение, добавляя статус выполнения
            try:
                # Получаем данные тренировки для обновления сообщения
                plan_data = training_manager.get_training_plan(plan_id)
                if plan_data and 'plan_data' in plan_data and 'training_days' in plan_data['plan_data']:
                    if day_num <= len(plan_data['plan_data']['training_days']):
                        day = plan_data['plan_data']['training_days'][day_num - 1]
                        formatted_day = f"✅ {format_training_day(day, day_num)}"
                        
                        # Пытаемся обновить сообщение
                        try:
                            await query.message.edit_text(formatted_day, parse_mode='Markdown')
                        except Exception as e:
                            logging.warning(f"Не удалось обновить сообщение: {e}")
            except Exception as e:
                logging.exception(f"Ошибка при обновлении сообщения: {e}")
        else:
            await query.message.reply_text("❌ Ошибка при отметке тренировки. Пожалуйста, попробуйте позже.")
    
    elif callback_data.startswith("cancel_training_"):
        # Отметка тренировки как отмененной
        parts = callback_data.split("_")
        plan_id = int(parts[2])
        day_num = int(parts[3])
        user_id = query.from_user.id
        
        # Отмечаем тренировку как отмененную
        training_manager = TrainingPlanManager(user_id)
        success = training_manager.mark_training_canceled(plan_id, day_num)
        
        if success:
            await query.message.reply_text(f"❌ Тренировка #{day_num} отмечена как пропущенная.")
            
            # Обновляем сообщение, добавляя статус отмены
            try:
                # Получаем данные тренировки для обновления сообщения
                plan_data = training_manager.get_training_plan(plan_id)
                if plan_data and 'plan_data' in plan_data and 'training_days' in plan_data['plan_data']:
                    if day_num <= len(plan_data['plan_data']['training_days']):
                        day = plan_data['plan_data']['training_days'][day_num - 1]
                        formatted_day = f"❌ {format_training_day(day, day_num)}"
                        
                        # Пытаемся обновить сообщение
                        try:
                            await query.message.edit_text(formatted_day, parse_mode='Markdown')
                        except Exception as e:
                            logging.warning(f"Не удалось обновить сообщение: {e}")
            except Exception as e:
                logging.exception(f"Ошибка при обновлении сообщения: {e}")
        else:
            await query.message.reply_text("❌ Ошибка при отметке тренировки. Пожалуйста, попробуйте позже.")

def setup_bot():
    """Configure and return the bot application."""
    # Создаем таблицы базы данных, если они не существуют
    create_tables()
    
    # Создаем экземпляр приложения
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CommandHandler("pending", pending_trainings_command))
    
    # Добавляем обработчик для кнопок
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Добавляем обработчик профиля
    profile_handler = RunnerProfileConversation()
    application.add_handler(profile_handler.get_conversation_handler())
    
    return application
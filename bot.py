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
        "/help - Показать это сообщение с командами\n\n"
        "Для начала работы и создания персонализированного плана тренировок, "
        "используйте команду /plan"
    )
    await update.message.reply_text(help_text)

async def pending_trainings_command(update, context):
    """Handler for the /pending command - shows only pending (not completed) trainings."""
    try:
        # Get user ID from database
        telegram_id = update.effective_user.id
        db_user_id = DBManager.get_user_id(telegram_id)

        if not db_user_id:
            # User not found, prompt to start a conversation
            await update.message.reply_text(
                "⚠️ Чтобы создать план тренировок, сначала нужно создать профиль бегуна. "
                "Используйте команду /plan и выберите 'Создать новый'."
            )
            return

        # Get latest training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        if not plan:
            await update.message.reply_text(
                "❌ У вас еще нет плана тренировок. Используйте команду /plan для его создания."
            )
            return

        # Get completed and canceled trainings
        plan_id = plan['id']
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days

        # Send plan overview
        await update.message.reply_text(
            f"✅ Ваш персонализированный план тренировок:\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )

        # Send only not completed or canceled training days
        has_pending_trainings = False
        for idx, day in enumerate(plan['plan_data']['training_days']):
            training_day_num = idx + 1

            # Skip completed and canceled training days
            if training_day_num in processed_days:
                continue

            has_pending_trainings = True

            day_message = (
                f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )

            # Create "Выполнено" and "Отменить" buttons for each training day
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
            ])

            await update.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        # If all trainings are completed or canceled, show a congratulation message with continue button
        if not has_pending_trainings:
            # Calculate total completed distance
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

            # Add total distance to user profile
            new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)

            # Create continue button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
            ])

            formatted_volume = format_weekly_volume(new_volume, str(total_distance))

            await update.message.reply_text(
                f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
                f"Хотите продолжить тренировки с учетом вашего прогресса?",
                reply_markup=keyboard
            )

    except Exception as e:
        logging.error(f"Error generating training plan: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
        )

async def generate_plan_command(update, context):
    """Handler for the /plan command."""
    try:
        # Get user ID from database
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name

        # Try to add/update user and get the ID
        db_user_id = DBManager.add_user(telegram_id, username, first_name, last_name)

        if not db_user_id:
            await update.message.reply_text("❌ Произошла ошибка при регистрации пользователя.")
            return

        # Check if user has a runner profile
        profile = DBManager.get_runner_profile(db_user_id)

        if not profile:
            # User doesn't have a profile yet, suggest to create one
            await update.message.reply_text(
                "⚠️ У вас еще нет профиля бегуна. Давайте создадим его!\n\n"
                "Для начала сбора данных, введите /plan"
            )
            return

        # Check if user already has a training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

        if plan:
            # User already has a plan, ask if they want to view it or create a new one
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ Посмотреть текущий план", callback_data="view_plan")],
                [InlineKeyboardButton("🆕 Создать новый план", callback_data="new_plan")]
            ])

            await update.message.reply_text(
                "У вас уже есть план тренировок. Что вы хотите сделать?",
                reply_markup=keyboard
            )
            return

        # Generate new training plan
        await update.message.reply_text("⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...")

        # Get OpenAI service and generate plan
        openai_service = OpenAIService()
        plan = openai_service.generate_training_plan(profile)

        # Save the plan to database
        plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

        if not plan_id:
            await update.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
            return

        # Send plan overview
        await update.message.reply_text(
            f"✅ Ваш персонализированный план тренировок готов!\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )

        # Send each training day with action buttons
        for idx, day in enumerate(plan['training_days']):
            training_day_num = idx + 1
            day_message = (
                f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )

            # Create "Выполнено" and "Отменить" buttons for each training day
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
            ])

            await update.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Error generating training plan: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
        )

async def callback_query_handler(update, context):
    """Handler for inline button callbacks."""
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    db_user_id = DBManager.get_user_id(telegram_id)

    # Обработка кнопки выполнения тренировки
    if query.data.startswith('complete_'):
        # Формат: complete_PLAN_ID_DAY_NUMBER
        try:
            _, plan_id, day_number = query.data.split('_')
            plan_id = int(plan_id)
            day_number = int(day_number)

            # Отмечаем тренировку как выполненную
            success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, day_number)

            if success:
                # Получаем план снова, чтобы увидеть обновленные отметки о выполнении
                plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                if not plan:
                    await query.message.reply_text("❌ Не удалось найти план тренировок.")
                    return

                # Получаем день тренировки
                day_idx = day_number - 1
                if day_idx < 0 or day_idx >= len(plan['plan_data']['training_days']):
                    await query.message.reply_text("❌ Неверный номер тренировки.")
                    return

                day = plan['plan_data']['training_days'][day_idx]

                # Обновляем сообщение с отметкой о выполнении
                day_message = (
                    f"✅ *День {day_number}: {day['day']} ({day['date']})* - ВЫПОЛНЕНО\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )

                try:
                    # Пытаемся обновить сообщение, если это возможно
                    await query.message.edit_text(day_message, parse_mode='Markdown')
                except Exception:
                    # Если не удается обновить, отправляем новое сообщение
                    await query.message.reply_text(
                        f"✅ Тренировка на день {day_number} отмечена как выполненная!"
                    )

                # Проверяем, все ли тренировки выполнены или отменены
                completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
                processed_days = completed_days + canceled_days

                # Количество тренировок в плане
                total_days = len(plan['plan_data']['training_days'])

                # Проверка, все ли тренировки выполнены или отменены
                has_pending_trainings = any(day_num not in processed_days for day_num in range(1, total_days + 1))

                # Если все тренировки выполнены или отменены, отправляем поздравительное сообщение
                if not has_pending_trainings:
                    # Расчет общего пройденного расстояния
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

                    # Обновление еженедельного объема в профиле пользователя
                    new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)

                    # Создание кнопки для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])

                    # Отправка сообщения пользователю
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {new_volume}.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.reply_text("❌ Не удалось отметить тренировку как выполненную.")

        except Exception as e:
            logging.error(f"Error marking training as completed: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")

    # Обработка кнопки отмены тренировки
    elif query.data.startswith('cancel_'):
        # Формат: cancel_PLAN_ID_DAY_NUMBER
        try:
            _, plan_id, day_number = query.data.split('_')
            plan_id = int(plan_id)
            day_number = int(day_number)

            # Отмечаем тренировку как отмененную
            success = TrainingPlanManager.mark_training_canceled(db_user_id, plan_id, day_number)

            if success:
                # Получаем план снова, чтобы увидеть обновленные отметки
                plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                if not plan:
                    await query.message.reply_text("❌ Не удалось найти план тренировок.")
                    return

                # Получаем день тренировки
                day_idx = day_number - 1
                if day_idx < 0 or day_idx >= len(plan['plan_data']['training_days']):
                    await query.message.reply_text("❌ Неверный номер тренировки.")
                    return

                day = plan['plan_data']['training_days'][day_idx]

                # Обновляем сообщение с отметкой об отмене
                day_message = (
                    f"❌ *День {day_number}: {day['day']} ({day['date']})* - ОТМЕНЕНО\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )

                try:
                    # Пытаемся обновить сообщение, если это возможно
                    await query.message.edit_text(day_message, parse_mode='Markdown')
                except Exception:
                    # Если не удается обновить, отправляем новое сообщение
                    await query.message.reply_text(
                        f"❌ Тренировка на день {day_number} отмечена как отмененная!"
                    )

                # Проверяем, все ли тренировки выполнены или отменены
                completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
                canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
                processed_days = completed_days + canceled_days

                # Количество тренировок в плане
                total_days = len(plan['plan_data']['training_days'])

                # Проверка, все ли тренировки выполнены или отменены
                has_pending_trainings = any(day_num not in processed_days for day_num in range(1, total_days + 1))

                # Если все тренировки выполнены или отменены, отправляем поздравительное сообщение
                if not has_pending_trainings:
                    # Расчет общего пройденного расстояния
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

                    # Обновление еженедельного объема в профиле пользователя
                    new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)

                    # Создание кнопки для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])

                    # Отправка сообщения пользователю
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {new_volume}.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.reply_text("❌ Не удалось отметить тренировку как отмененную.")

        except Exception as e:
            logging.error(f"Error marking training as canceled: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")

    elif query.data == 'view_plan':
        # Show existing plan
        try:
            # Получаем ID пользователя из базы данных
            telegram_id = update.effective_user.id
            db_user_id = DBManager.get_user_id(telegram_id)

            if not db_user_id:
                await query.message.reply_text(
                    "⚠️ Для создания плана тренировок сначала нужно создать профиль бегуна. "
                    "Используйте команду /start"
                )
                return

            # Получаем последний план пользователя
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            if not plan:
                await query.message.reply_text(
                    "❌ У вас еще нет плана тренировок. Используйте команду /plan для его создания."
                )
                return

            await query.message.reply_text(
                f"✅ Ваш персонализированный план тренировок:\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )

            # Get completed and canceled trainings
            plan_id = plan['id']
            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            processed_days = completed_days + canceled_days

            # Send only not completed or canceled training days
            has_pending_trainings = False
            for idx, day in enumerate(plan['plan_data']['training_days']):
                training_day_num = idx + 1

                # Skip completed and canceled training days
                if training_day_num in processed_days:
                    continue

                has_pending_trainings = True

                day_message = (
                    f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )

                # Create "Выполнено" and "Отменить" buttons for each training day
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                ])

                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

            # If all trainings are completed or canceled, show a congratulation message with continue button
            if not has_pending_trainings:
                # Calculate total completed distance
                total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

                # Add total distance to user profile
                new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)

                # Create continue button
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                ])

                await query.message.reply_text(
                    f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                    f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {new_volume}.\n\n"
                    f"Хотите продолжить тренировки с учетом вашего прогресса?",
                    reply_markup=keyboard
                )

        except Exception as e:
            logging.error(f"Error viewing training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при отображении плана тренировок.")


    elif query.data.startswith('continue_plan_'):
        # Format: continue_plan_PLAN_ID
        try:
            # Extract plan ID
            _, plan_id = query.data.split('_', 2)[1:]
            plan_id = int(plan_id)

            await query.message.reply_text("⏳ Генерирую продолжение плана тренировок на основе ваших достижений. Это может занять некоторое время...")

            # Get runner profile and the current plan
            profile = DBManager.get_runner_profile(db_user_id)
            current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            if not profile or not current_plan:
                await query.message.reply_text("❌ Не удалось найти ваш профиль или текущий план тренировок.")
                return

            # Calculate total completed distance
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

            # Generate continuation of the training plan
            openai_service = OpenAIService()
            plan = openai_service.generate_training_plan_continuation(profile, total_distance, current_plan['plan_data'])

            # Save the new plan to database
            new_plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

            if not new_plan_id:
                await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                return

            # Send plan overview
            await query.message.reply_text(
                f"✅ Ваш новый персонализированный план тренировок готов!\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )

            # Send training days
            for idx, day in enumerate(plan['training_days']):
                training_day_num = idx + 1

                day_message = (
                    f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                    f"Тип: {day['training_type']}\n"
                    f"Дистанция: {day['distance']}\n"
                    f"Темп: {day['pace']}\n\n"
                    f"{day['description']}"
                )

                # Create "Выполнено" and "Отменить" buttons for each training day
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{new_plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{new_plan_id}_{training_day_num}")]
                ])

                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        except Exception as e:
            logging.error(f"Error generating training plan continuation: {e}")
            await query.message.reply_text("❌ Произошла ошибка при генерации продолжения плана. Пожалуйста, попробуйте позже.")

    elif query.data == 'new_plan' or query.data == 'generate_plan':
        # Generate new plan
        await query.message.reply_text("⏳ Генерирую новый персонализированный план тренировок. Это может занять некоторое время...")

        # Get runner profile
        profile = DBManager.get_runner_profile(db_user_id)

        # Generate new training plan
        openai_service = OpenAIService()
        plan = openai_service.generate_training_plan(profile)

        # Save plan to database
        plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

        if not plan_id:
            await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
            return

        # Send plan overview
        await query.message.reply_text(
            f"✅ Ваш новый персонализированный план тренировок готов!\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}",
            parse_mode='Markdown'
        )

        # Get completed and canceled trainings
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days

        # Send only not completed or canceled training days
        has_pending_trainings = False
        for idx, day in enumerate(plan['training_days']):
            training_day_num = idx + 1

            # Skip completed and canceled training days
            if training_day_num in processed_days:
                continue

            has_pending_trainings = True

            day_message = (
                f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                f"Тип: {day['training_type']}\n"
                f"Дистанция: {day['distance']}\n"
                f"Темп: {day['pace']}\n\n"
                f"{day['description']}"
            )

            # Create "Выполнено" and "Отменить" buttons for each training day
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
            ])

            await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        # If all trainings are completed or canceled, show a congratulation message with continue button
        if not has_pending_trainings:
            # Calculate total completed distance
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

            # Add total distance to user profile
            new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)

            # Create continue button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
            ])

            await query.message.reply_text(
                f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {new_volume}.\n\n"
                f"Хотите продолжить тренировки с учетом вашего прогресса?",
                reply_markup=keyboard
            )

def setup_bot():
    """Configure and return the bot application."""
    if not TELEGRAM_TOKEN:
        logging.critical("Telegram bot token is missing! Set the TELEGRAM_TOKEN environment variable.")
        raise ValueError("Telegram bot token is required")

    # Create database tables
    create_tables()

    # Initialize the bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Set up conversation handler
    conversation = RunnerProfileConversation()
    application.add_handler(conversation.get_conversation_handler())

    # Add standalone command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CommandHandler("pending", pending_trainings_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    return application
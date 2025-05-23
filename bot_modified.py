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


async def send_main_menu(update, context, message_text="Что вы хотите сделать?"):
    """Отправляет главное меню с кнопками."""
    # Создаем кнопки в стиле ReplyKeyboardMarkup как на скриншоте
    keyboard = ReplyKeyboardMarkup([
        ["👁️ Посмотреть текущий план"],
        ["🆕 Создать новый план"],
        ["✏️ Обновить мой профиль"],
        ["🏃‍♂️ Показать мой профиль"]
    ], resize_keyboard=True)

    # Отправляем сообщение с кнопками
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(message_text, reply_markup=keyboard)
    else:
        await update.message.reply_text(message_text, reply_markup=keyboard)


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


def format_training_day(day, training_day_num):
    """
    Форматирует день тренировки в стиле зеленого текста на черном фоне,
    как показано на скриншоте. Адаптирует любой формат в улучшенную структуру.
    
    Args:
        day: Словарь с данными о дне тренировки
        training_day_num: Номер дня тренировки
        
    Returns:
        str: Отформатированное сообщение о дне тренировки
    """
    # Базовые данные, которые должны быть в любом случае
    day_date = day.get('date', 'Дата не указана')
    day_name = day.get('day', 'День не указан')
    training_type = day.get('training_type', 'Тип не указан')
    distance = day.get('distance', 'Дистанция не указана')
    pace = day.get('pace', 'Темп не указан')
    
    # Извлекаем километраж из строки дистанции (например, "8 км" -> "8")
    # или из целочисленного значения
    km_value = ""
    if isinstance(distance, str):
        import re
        km_match = re.search(r'(\d+(?:\.\d+)?)', distance)
        if km_match:
            km_value = km_match.group(1)
    elif isinstance(distance, (int, float)):
        km_value = str(distance)
    
    km_text = f" ({km_value} км)" if km_value else ""
    
    # Получаем описание и цель тренировки
    description = day.get('description', '')
    purpose = day.get('purpose', '')
    
    # Извлекаем информацию о разминке, основной части и заминке
    warmup_details = []
    main_workout_details = []
    cooldown_details = []
    
    # Определяем тип разминки и заминки на основе типа тренировки
    warmup_distance = "2 км"
    cooldown_distance = "1 км"
    
    if "интервал" in training_type.lower():
        warmup_distance = "2 км"
        cooldown_distance = "1 км"
    elif "темпов" in training_type.lower():
        warmup_distance = "2 км"
        cooldown_distance = "2 км"
    elif "длительн" in training_type.lower():
        warmup_distance = "1.5 км"
        cooldown_distance = "1 км"
    elif "восстанов" in training_type.lower():
        warmup_distance = "0.5 км"
        cooldown_distance = "0.5 км"
    
    # Анализируем описание для получения деталей
    if "Разминка:" in description or "разминка:" in description:
        # План уже имеет структурированное описание, извлекаем его
        if "Разминка:" in description:
            warmup_text = description.split("Разминка:")[1].split("Основная часть:")[0].strip() if "Основная часть:" in description else description.split("Разминка:")[1].strip()
        else:
            warmup_text = description.split("разминка:")[1].split("Основная часть:")[0].strip() if "Основная часть:" in description else description.split("разминка:")[1].strip()
        
        # Разделяем на пункты, если они есть
        warmup_details = [item.strip() for item in warmup_text.split('.') if item.strip()]
    else:
        # Создаем стандартные пункты разминки
        warmup_details = [
            f"10-15 минут легкого бега (темп 5:30-6:00 мин/км)",
            "3-4 динамических упражнения (высокие колени, захлесты голени)",
            f"2-3 ускорения по 30 секунд (темп около 4:30 мин/км)"
        ]
    
    # Извлекаем основную часть
    if "Основная часть:" in description or "основная часть:" in description:
        if "Основная часть:" in description:
            main_text = description.split("Основная часть:")[1].split("Заминка:")[0].strip() if "Заминка:" in description else description.split("Основная часть:")[1].strip()
        else:
            main_text = description.split("основная часть:")[1].split("Заминка:")[0].strip() if "Заминка:" in description else description.split("основная часть:")[1].strip()
        
        # Разделяем на пункты, если они есть
        main_workout_details = [item.strip() for item in main_text.split('.') if item.strip()]
    else:
        # Определяем содержание основной части на основе типа тренировки
        if "интервал" in training_type.lower():
            main_workout_details = [
                f"6 интервалов по 800м в темпе 4:10-4:20 мин/км",
                f"Отдых между интервалами: медленный бег 400м (5:45-6:00 мин/км)",
                f"Важно: поддерживайте ровное усилие на всех интервалах"
            ]
        elif "темпов" in training_type.lower():
            main_workout_details = [
                f"{int(km_value) - 4 if km_value else 6} км непрерывного бега в марафонском темпе: 4:40-4:50 мин/км",
                f"Фокус: поддержание стабильного темпа без ускорений и замедлений",
                f"Пульс должен оставаться в зоне 80-85% от максимума"
            ]
        elif "длительн" in training_type.lower():
            main_workout_details = [
                f"Бег в комфортном темпе на всей дистанции",
                f"Фокус: аэробная выносливость и экономичность бега",
                f"Следите за техникой и равномерным дыханием"
            ]
        else:
            main_workout_details = [
                f"Равномерный бег в комфортном темпе",
                f"Контролируйте дыхание и следите за техникой"
            ]
    
    # Извлекаем заминку
    if "Заминка:" in description or "заминка:" in description:
        if "Заминка:" in description:
            cooldown_text = description.split("Заминка:")[1].strip()
        else:
            cooldown_text = description.split("заминка:")[1].strip()
        
        # Разделяем на пункты, если они есть
        cooldown_details = [item.strip() for item in cooldown_text.split('.') if item.strip()]
    else:
        # Создаем стандартные пункты заминки
        cooldown_details = [
            f"5-10 минут очень легкого бега (темп 6:00+ мин/км)",
            f"Короткая растяжка основных мышечных групп"
        ]
    
    # Создаем цель тренировки, если она указана
    if not purpose:
        # Определяем цель на основе типа тренировки
        if "интервал" in training_type.lower():
            purpose = "развитие лактатного порога, улучшение скоростной выносливости"
        elif "темпов" in training_type.lower():
            purpose = "развитие выносливости на уровне марафонского темпа"
        elif "длительн" in training_type.lower():
            purpose = "развитие аэробной выносливости и экономичности бега"
        elif "восстанов" in training_type.lower():
            purpose = "активное восстановление, поддержание объема"
        else:
            purpose = "общее развитие выносливости"
    
    # Создаем текст физиологической цели
    physio_goal = ""
    if "интервал" in training_type.lower():
        physio_goal = ("Эта тренировка нацелена на повышение лактатного "
                      "порога - способности организма эффективно утилизировать лактат при высокой "
                      "интенсивности. По методике Джека Дэниелса, интервалы 800м с интенсивностью "
                      "85-90% от максимума оптимально стимулируют улучшение аэробной мощности и "
                      "лактатного порога.")
    elif "темпов" in training_type.lower():
        physio_goal = ("По методике Стива Магнесса, темповые пробежки на "
                      "уровне марафонского темпа тренируют мышечную эффективность и "
                      "метаболическую адаптацию именно к тому темпу, который потребуется "
                      "поддерживать на соревновании. Это улучшает экономичность бега и "
                      "психологическую уверенность.")
    elif "длительн" in training_type.lower():
        physio_goal = ("Длительные пробежки развивают митохондриальную плотность, "
                      "капилляризацию мышц и эффективность использования жиров в качестве "
                      "топлива. Это критически важно для марафонской дистанции, где ваше тело "
                      "должно экономно расходовать гликоген.")
    elif "восстанов" in training_type.lower():
        physio_goal = ("Восстановительные пробежки усиливают кровоток в мышцах, "
                      "удаляя продукты распада и ускоряя доставку питательных веществ. "
                      "Такие тренировки критически важны для общего прогресса и профилактики "
                      "перетренированности.")
        
    # Создаем советы по выполнению
    execution_tips = []
    if "интервал" in training_type.lower():
        execution_tips = [
            "Выполняйте на ровной поверхности (стадион идеален)",
            "Контролируйте темп через пульс (не должен превышать 90% от максимума)",
            "Концентрируйтесь на поддержании техники даже при нарастающей усталости",
            "Не превышайте рекомендуемый темп в первых интервалах"
        ]
    elif "темпов" in training_type.lower():
        execution_tips = [
            "Первый километр темповой части начните на 5-10 секунд медленнее целевого темпа",
            "Следите за ровным дыханием (желательно ритм 3 шага вдох / 3 шага выдох)",
            "Гидратация: маленький глоток воды перед стартом темповой части"
        ]
    elif "длительн" in training_type.lower():
        execution_tips = [
            "Выберите маршрут без крутых подъемов для первой половины дистанции",
            "Старайтесь поддерживать одинаковое усилие, а не темп, на подъемах и спусках",
            "Гидратация и питание: вода каждые 20-30 минут, гель/бар после 1-1.5 часов"
        ]
    elif "восстанов" in training_type.lower():
        execution_tips = [
            "Темп должен быть действительно легким - вы должны комфортно разговаривать",
            "Отслеживайте пульс - он не должен превышать 65-70% от максимума",
            "Фокусируйтесь на технике и расслаблении плечевого пояса"
        ]
    
    # Форматируем главный заголовок тренировки с датой
    date_str = f" ({day_date})" if day_date and day_date != 'Дата не указана' else ""
    header = f"{day_name.upper()}{date_str}: {training_type.upper()}{km_text}"
    
    # Форматируем структурированное описание тренировки
    formatted_description = []
    formatted_description.append(f"Задачи: {purpose}")
    formatted_description.append("\nСтруктура тренировки:")
    
    # Добавляем разминку
    formatted_description.append(f"\n1. Разминка ({warmup_distance}):")
    for item in warmup_details:
        formatted_description.append(f"• {item}")
    
    # Вычисляем дистанцию основной части
    main_distance = ""
    try:
        total_km = float(km_value) if km_value else 0
        warmup_km = float(warmup_distance.split()[0]) if warmup_distance else 0
        cooldown_km = float(cooldown_distance.split()[0]) if cooldown_distance else 0
        main_km = total_km - warmup_km - cooldown_km
        if main_km > 0:
            main_distance = f"{main_km} км"
    except:
        main_distance = "?"
    
    # Добавляем основную часть
    formatted_description.append(f"\n2. Основная часть ({main_distance}):")
    for item in main_workout_details:
        formatted_description.append(f"• {item}")
    
    # Добавляем заминку
    formatted_description.append(f"\n3. Заминка ({cooldown_distance}):")
    for item in cooldown_details:
        formatted_description.append(f"• {item}")
    
    # Добавляем физиологическую цель
    if physio_goal:
        formatted_description.append(f"\nФизиологическая цель: {physio_goal}")
    
    # Добавляем советы по выполнению
    if execution_tips:
        formatted_description.append("\nСоветы по выполнению:")
        for tip in execution_tips:
            formatted_description.append(f"• {tip}")
    
    # Финальное сообщение с форматированием
    formatted_message = f"*{header}*\n" + "\n".join(formatted_description)
    
    return formatted_message

async def help_command(update, context):
    """Handler for the /help command."""
    # Добавим проверку работы часовых поясов
    from datetime import datetime, timedelta
    import pytz

    # Получим текущее время в UTC
    utc_now = datetime.now(pytz.UTC)

    # Преобразуем в московское время
    moscow_tz = pytz.timezone('Europe/Moscow')
    moscow_now = utc_now.astimezone(moscow_tz)

    # Логирование и отображение времени для отладки
    logging.info(f"Текущее время (UTC): {utc_now.strftime('%d.%m.%Y %H:%M:%S')}")
    logging.info(f"Текущее время (Москва): {moscow_now.strftime('%d.%m.%Y %H:%M:%S')}")

    # Генерируем даты для следующих 7 дней
    dates = []
    for i in range(7):
        date = moscow_now + timedelta(days=i)
        dates.append(date.strftime("%d.%m.%Y"))

    logging.info(f"Сгенерированные даты для трейнингов: {dates}")

    help_text = (
        "👋 Привет! Я бот-помощник для бегунов. Вот что я могу:\n\n"
        "/plan - Создать или просмотреть план тренировок\n"
        "/pending - Показать только незавершенные тренировки\n"
        "/update - Обновить ваш профиль бегуна\n"
        "/help - Показать это сообщение с командами\n\n"
        "📱 Вы также можете отправить мне скриншот из вашего трекера тренировок (Nike Run, Strava, Garmin и др.), "
        "и я автоматически проанализирую его и зачту вашу тренировку!\n\n"
        "Для начала работы и создания персонализированного плана тренировок, "
        "используйте команду /plan\n\n"
        f"Текущая дата и время (Москва): {moscow_now.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"Даты для тренировок: {', '.join(dates[:3])}..."
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
            
            # Используем функцию форматирования тренировочного дня
            day_message = format_training_day(day, training_day_num)

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

            # Format the weekly volume
            formatted_volume = format_weekly_volume(new_volume, str(total_distance))

            # Create continue button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
            ])

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

        # Проверяем статус оплаты пользователя
        payment_status = DBManager.get_payment_status(db_user_id)
        if not payment_status or not payment_status.get('payment_agreed', False):
            # Если пользователь ещё не выбрал вариант оплаты
            if not context.user_data.get('awaiting_payment_confirmation', False) and context.user_data.get('payment_agreed') is None:
                reply_markup = ReplyKeyboardMarkup(
                    [
                        ['Да, буду платить 500 рублей в месяц'],
                        ['Нет. Я и так МАШИНА Ой БОЙ!']
                    ],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )

                await update.message.reply_text(
                    "Этот бот создан с любовью к моей невесте Пумпуне ❤️, а она очень хочет поехать " + 
                    "на Лондонский Марафон 2026 года. Поэтому бот стоит 500 рублей в месяц с " + 
                    "гарантией добавления новых фичей и легкой отменой подписки!",
                    reply_markup=reply_markup
                )

                # Сохраняем состояние - ожидаем ответа на вопрос об оплате
                context.user_data['awaiting_payment_confirmation'] = True
                return
            # Если пользователь отказался от оплаты
            elif context.user_data.get('payment_agreed') == False:
                await update.message.reply_text(
                    "Очень жаль, но я скоро сделаю простую бесплатную версию и пришлю ее тебе"
                )
                return
            # Если статуса оплаты нет в БД, но есть в пользовательских данных
            elif context.user_data.get('payment_agreed', False):
                # Сохраняем статус оплаты в БД
                DBManager.save_payment_status(db_user_id, True)
            else:
                # Предлагаем оплату снова
                reply_markup = ReplyKeyboardMarkup(
                    [
                        ['Да, буду платить 500 рублей в месяц'],
                        ['Нет. Я и так МАШИНА Ой БОЙ!']
                    ],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )

                await update.message.reply_text(
                    "Для доступа к функции создания плана тренировок необходимо оформить подписку. " +
                    "Бот стоит 500 рублей в месяц с гарантией добавления новых фичей и легкой отменой!",
                    reply_markup=reply_markup
                )

                # Сохраняем состояние - ожидаем ответа на вопрос об оплате
                context.user_data['awaiting_payment_confirmation'] = True
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

        # Проверяем, что пользователь согласился на оплату, если это его первый план
        if context.user_data.get('awaiting_payment_confirmation', False):
            await update.message.reply_text(
                "Пожалуйста, сначала ответьте на вопрос об оплате, чтобы продолжить."
            )
            return

        if not context.user_data.get('payment_agreed', False):
            # Это первый вызов для генерации плана после создания профиля
            # Проверяем, был ли отказ от оплаты
            if context.user_data.get('payment_agreed') == False:  # Именно False, а не None
                await update.message.reply_text(
                    "Очень жаль, но я скоро сделаю простую бесплатную версию и пришлю ее тебе"
                )
                return

            # Если payment_agreed отсутствует, вероятно пользователь ещё не видел вопрос
            # Это не должно произойти, но на всякий случай обрабатываем
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Да, буду платить 500 рублей в месяц'],
                    ['Нет. Я и так МАШИНА Ой БОЙ!']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )

            await update.message.reply_text(
                "Этот бот создан с любовью к моей невесте Пумпуне ❤️, а она очень хочет поехать " + 
                "на Лондонский Марафон 2026 года. Поэтому бот стоит 500 рублей в месяц с " + 
                "гарантией добавления новых фичей и легкой отменой подписки!",
                reply_markup=reply_markup
            )

            # Сохраняем состояние - ожидаем ответа на вопрос об оплате
            context.user_data['awaiting_payment_confirmation'] = True
            return

        # Generate new training plan
        await update.message.reply_text("⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...")

        try:
            # Пробуем использовать новый MCP-инструмент через адаптер
            from agent.adapter import AgentAdapter
            agent_adapter = AgentAdapter()
            plan = agent_adapter.generate_training_plan(profile)
            logging.info("План успешно создан через MCP-инструмент")
        except Exception as e:
            logging.error(f"Ошибка при использовании MCP-инструмента: {e}")
            # В случае ошибки возвращаемся к старому методу
            openai_service = OpenAIService()
            plan = openai_service.generate_training_plan(profile)
            logging.info("План создан через оригинальный OpenAIService после ошибки MCP")

        # Save the plan to database
        plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

        if not plan_id:
            await update.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
            return

        # Send plan overview with info about screenshot uploads
        await update.message.reply_text(
            f"✅ Ваш персонализированный план тренировок готов!\n\n"
            f"*{plan['plan_name']}*\n\n"
            f"{plan['plan_description']}\n\n"
            f"📱 Совет: вы можете просто присылать мне скриншоты из вашего трекера тренировок "
            f"(Nike Run, Strava, Garmin и др.), и я автоматически проанализирую результаты "
            f"и зачту вашу тренировку!",
            parse_mode='Markdown'
        )

        # Send each training day with action buttons
        for idx, day in enumerate(plan['training_days']):
            training_day_num = idx + 1
            day_message = format_training_day(day, training_day_num)

            # Create "Выполнено" and "Отменить" buttons for each training day
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
            ])

            await update.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        # Отправляем приглашение в чат БЕТА тестеров
        await update.message.reply_text("Если есть желание и время заходите в чатик БЕТА тестеров https://t.me/+oiEFpRKHRPA3ZDA6")

        # После отправки всех дней тренировки, показываем главное меню
        await send_main_menu(update, context, "Ваш план создан. Что еще вы хотите сделать?")

    except Exception as e:
        logging.error(f"Error generating training plan: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
        )
        # Показываем главное меню в случае ошибки
        await send_main_menu(update, context)

async def update_profile_command(update, context):
    """Handler for the /update command - starts runner profile update dialog."""
    user = update.effective_user
    telegram_id = user.id
    logging.info(f"Начато обновление профиля для пользователя {telegram_id}")

    # Проверяем наличие пользователя в БД
    db_user_id = DBManager.get_user_id(telegram_id)

    if not db_user_id:
        # Пользователь еще не зарегистрирован
        message_text = "Похоже, вы еще не создали профиль бегуна. Используйте команду /start, чтобы начать."
        if hasattr(update, 'callback_query'):
            await update.callback_query.message.reply_text(message_text)
            await update.callback_query.answer()
        else:
            await update.message.reply_text(message_text)
        return

    # Создаем объект для работы с профилем
    from conversation import RunnerProfileConversation
    profile_conv = RunnerProfileConversation()

    try:
        # Инициализируем обновление профиля с учетом источника вызова
        if hasattr(update, 'callback_query'):
            # Отправляем сообщение о начале обновления профиля
            sent_message = await update.callback_query.message.reply_text(
                "✏️ Давайте обновим ваш профиль бегуна. "
                "Я буду задавать вопросы, а вы отвечайте на них.\n\n"
                "Вы можете отменить процесс в любой момент, отправив команду /cancel."
            )
            
            # Отвечаем на callback, чтобы пользователь видел, что кнопка была нажата
            await update.callback_query.answer()
            
            # Сохраняем информацию о том, что идет обновление профиля
            context.user_data['profile_update_in_progress'] = True
            
            # Запускаем диалог обновления профиля напрямую
            # Передаем флаг is_callback=True, чтобы обработать правильно
            await profile_conv.start_update(update, context)
        else:
            # Если вызвано из текстовой команды
            await profile_conv.start_update(update, context)
        
        logging.info(f"Запущен диалог обновления профиля для пользователя {telegram_id}")
    except Exception as e:
        # Логируем ошибку и информируем пользователя
        logging.error(f"Ошибка при запуске обновления профиля: {e}")
        error_text = "Произошла ошибка при запуске обновления профиля. Пожалуйста, попробуйте позже."
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.message.reply_text(error_text)
        else:
            await update.message.reply_text(error_text)
            
        # Очищаем все временные данные о процессе
        if 'profile_update_in_progress' in context.user_data:
            del context.user_data['profile_update_in_progress']

async def callback_query_handler(update, context):
    """Handler for inline button callbacks."""
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    db_user_id = DBManager.get_user_id(telegram_id)

    # Запоминаем callback_data для возможного восстановления после выполнения действия
    original_callback_data = query.data
    context.user_data['last_callback'] = original_callback_data
    
    # Проверяем, не является ли это выбором марафона
    if query.data == "select_marathon":
        # Импортируем функцию для выбора марафона
        from marathon_utils import get_marathons_list
        
        # Получаем список марафонов
        marathons = get_marathons_list()
        
        # Создаем клавиатуру с марафонами
        keyboard = []
        for i, marathon in enumerate(marathons[:10]):  # Показываем только первые 10 марафонов
            # Формируем callback_data в формате: set_marathon_YYYY-MM-DD
            callback_data = f"set_marathon_{marathon['Дата']}"
            # Добавляем кнопку с названием и датой марафона
            button = InlineKeyboardButton(
                f"{marathon['Название']} ({marathon['Дата']})", 
                callback_data=callback_data
            )
            keyboard.append([button])
        
        # Добавляем кнопку отмены
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_marathon_selection")])
        
        # Создаем разметку клавиатуры
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение с выбором марафона
        await query.message.reply_text(
            "Выберите марафон из списка:",
            reply_markup=reply_markup
        )
        return
        
    # Проверяем, не является ли это выбором даты марафона
    if query.data.startswith("set_marathon_"):
        # Извлекаем дату из callback_data
        date_str = query.data.replace("set_marathon_", "")
        
        # Получаем профиль пользователя
        profile = DBManager.get_runner_profile(db_user_id)
        if not profile:
            await query.message.reply_text(
                "❌ Не удалось найти ваш профиль. "
                "Пожалуйста, создайте профиль заново."
            )
            return
            
        # Обновляем дату соревнования в профиле
        profile["competition_date"] = date_str
        DBManager.save_runner_profile(db_user_id, profile)
        
        # Отправляем сообщение об успешном обновлении
        await query.message.reply_text(
            f"✅ Дата соревнования успешно обновлена на {date_str}."
        )
        
        # Показываем главное меню
        await send_main_menu(update, context, 
            "Теперь вы можете получить персонализированный план тренировок, основанный на вашем профиле."
        )
        return
        
    # Проверяем, не является ли это отменой выбора марафона
    if query.data == "cancel_marathon_selection":
        await query.message.reply_text(
            "Выбор марафона отменен. Вы можете обновить дату соревнования позже через меню обновления профиля."
        )
        
        # Показываем главное меню
        await send_main_menu(update, context, "Что вы хотите сделать?")
        return

    # Обработка кнопок подтверждения создания нового плана
    if query.data == "confirm_new_plan" or query.data == "new_plan":
        # Получаем ID пользователя
        telegram_id = update.effective_user.id
        db_user_id = DBManager.get_user_id(telegram_id)

        # Проверяем статус активной подписки
        active_subscription = DBManager.check_active_subscription(db_user_id)

        # Если в БД нет записи о подписке, но пользователь согласился на оплату 
        # в текущей сессии, создаем запись в БД
        if not active_subscription and context.user_data.get('payment_agreed', False):
            DBManager.save_payment_status(db_user_id, True)
            active_subscription = True

        # Проверяем статус оплаты для создания плана
        if context.user_data.get('awaiting_payment_confirmation', False):
            await query.message.reply_text(
                "Пожалуйста, сначала ответьте на вопрос об оплате, чтобы продолжить."
            )
            return

        if not active_subscription and not context.user_data.get('payment_agreed', False):
            # Это первый вызов для генерации плана после создания профиля
            # Проверяем, был ли отказ от оплаты
            if context.user_data.get('payment_agreed') == False:  # Именно False, а не None
                await query.message.reply_text(
                    "Очень жаль, но я скоро сделаю простую бесплатную версию и пришлю ее тебе"
                )
                return

            # Если payment_agreed отсутствует, вероятно пользователь ещё не видел вопрос
            # Это не должно произойти, но на всякий случай обрабатываем
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Да, буду платить 500 рублей в месяц'],
                    ['Нет. Я и так МАШИНА Ой БОЙ!']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )

            await query.message.reply_text(
                "Этот бот создан с любовью к моей невесте Пумпуне ❤️, а она очень хочет поехать " + 
                "на Лондонский Марафон 2026 года. Поэтому бот стоит 500 рублей в месяц с " + 
                "гарантией добавления новых фичей и легкой отменой подписки!",
                reply_markup=reply_markup
            )

            # Сохраняем состояние - ожидаем ответа на вопрос об оплате
            context.user_data['awaiting_payment_confirmation'] = True
            return

        # Пользователь подтвердил создание нового плана с теми же параметрами
        # Отправляем сообщение с котиком
        with open("attached_assets/котик.jpeg", "rb") as photo:
            await query.message.reply_photo(
                photo=photo,
                caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
            )

        # Получаем профиль пользователя
        profile = DBManager.get_runner_profile(db_user_id)

        # Генерируем новый план
        try:
            # Генерируем план
            try:
                # Пробуем использовать новый MCP-инструмент через адаптер
                from agent.adapter import AgentAdapter
                agent_adapter = AgentAdapter()
                plan = agent_adapter.generate_training_plan(profile)
                logging.info("План успешно создан через MCP-инструмент")
            except Exception as e:
                logging.error(f"Ошибка при использовании MCP-инструмента: {e}")
                # В случае ошибки возвращаемся к старому методу
                openai_service = OpenAIService()
                plan = openai_service.generate_training_plan(profile)
                logging.info("План создан через оригинальный OpenAIService после ошибки MCP")

            # Сохраняем план в БД
            plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

            if not plan_id:
                await query.message.reply_text(
                    "❌ Произошла ошибка при сохранении плана тренировок."
                )
                return

            # Получаем сохраненный план
            saved_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            # Отправляем план пользователю
            await query.message.reply_text(
                f"✅ Ваш персонализированный план тренировок готов!\n\n"
                f"*{saved_plan['plan_name']}*\n\n"
                f"{saved_plan['plan_description']}",
                parse_mode='Markdown'
            )

            # Отправляем приглашение в чат БЕТА тестеров
            await query.message.reply_text("Если есть желание и время заходите в чатик БЕТА тестеров https://t.me/+oiEFpRKHRPA3ZDA6")

            # Показываем главное меню после генерации плана
            await send_main_menu(update, context, "Ваш план создан. Что еще вы хотите сделать?")

            # Отправляем дни тренировок
            # Определяем структуру плана
            training_days = []
            if 'training_days' in saved_plan:
                training_days = saved_plan['training_days']
            elif 'plan_data' in saved_plan and isinstance(saved_plan['plan_data'], dict) and 'training_days' in saved_plan['plan_data']:
                training_days = saved_plan['plan_data']['training_days']
            else:
                logging.error(f"Неверная структура плана: {saved_plan.keys()}")
                await query.message.reply_text("❌ Ошибка в структуре плана тренировок.")
                return

            for idx, day in enumerate(training_days):
                training_day_num = idx + 1

                # Используем форматирование тренировочного дня для согласованного вида
                training_message = format_training_day(day, training_day_num)

                # Добавляем кнопки
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", 
                                         callback_data=f"complete_{saved_plan['id']}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", 
                                         callback_data=f"cancel_{saved_plan['id']}_{training_day_num}")]
                ])

                await query.message.reply_text(
                    training_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )

        except Exception as e:
            logging.error(f"Ошибка генерации плана: {e}")
            await query.message.reply_text(
                "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
            )

            # Показываем главное меню после ошибки генерации плана
            await send_main_menu(update, context, "Что вы хотите сделать?")

        return

    elif query.data == "update_profile_first":
        # Пользователь решил сначала обновить профиль
        # Отправляем сообщение и запускаем обновление профиля напрямую
        # используя конверсейшн-хэндлер из профиля
        from conversation import RunnerProfileConversation
        profile_conv = RunnerProfileConversation()

        # Сообщаем пользователю, что начинаем обновление профиля
        await query.message.reply_text(
            "✏️ Начинаем обновление профиля бегуна.\n\n"
            "Я буду задавать вопросы о ваших параметрах. "
            "Вы можете отменить процесс в любой момент, отправив команду /cancel."
        )

        # Получаем профиль пользователя
        runner_profile = DBManager.get_runner_profile(db_user_id)

        # Формируем клавиатуру для выбора дистанции
        from telegram import ReplyKeyboardMarkup
        reply_markup = ReplyKeyboardMarkup(
            [['5', '10'], ['21', '42']], 
            one_time_keyboard=True,
            resize_keyboard=True
        )

        # Отправляем начальное сообщение с запросом дистанции
        msg = await query.message.reply_text(
            f"Текущая дистанция: {runner_profile.get('distance', 'Не указано')} км\n"
            f"Введите новую целевую дистанцию (в км):",
            reply_markup=reply_markup
        )

        # Настраиваем данные контекста для обработки диалога
        context.user_data['db_user_id'] = db_user_id
        context.user_data['profile_data'] = {}
        context.user_data['is_profile_update'] = True

        # Устанавливаем текущее состояние диалога
        from conversation import STATES
        # Добавляем обработчик в диспетчер
        update._effective_user = update.effective_user
        update._effective_message = msg

        return STATES['DISTANCE']

    elif query.data == "cancel_new_plan":
        # Пользователь отменил создание нового плана
        await query.message.reply_text("Создание нового плана отменено.")
        await send_main_menu(update, context, "Что вы хотите сделать?")
        return

    # Обработка кнопки "Помощь"
    if query.data == "help":
        help_text = (
            "👋 Привет! Я бот-помощник для бегунов. Вот что я могу:\n\n"
            "/plan - Создать или просмотреть план тренировок\n"
            "/pending - Показать только незавершенные тренировки\n"
            "/update - Обновить ваш профиль бегуна\n"
            "/help - Показать это сообщение с командами\n\n"
            "📱 Вы также можете отправить мне скриншот из вашего трекера тренировок (Nike Run, Strava, Garmin и др.), "
            "и я автоматически проанализирую его и зачту вашу тренировку!"
        )
        await query.message.reply_text(help_text)

        # Показываем меню после справки
        await send_main_menu(update, context)
        return

    # Обработка кнопки "Обновить мой профиль" в профиле (обрабатывается в ConversationHandler)

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

                # Используем функцию форматирования для согласованного вида
                day_message = format_training_day(day, day_number)
                # Добавляем отметку о выполнении
                day_message = "✅ " + day_message.strip() + " - ВЫПОЛНЕНО"

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

                    # Форматирование объема бега для отображения
                    formatted_volume = format_weekly_volume(new_volume, str(total_distance))

                    # Создание кнопки для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])

                    # Отправка сообщения пользователю
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
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

                # Используем функцию форматирования для согласованного вида
                day_message = format_training_day(day, day_number)
                # Добавляем отметку об отмене
                day_message = "❌ " + day_message.strip() + " - ОТМЕНЕНО"

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

                    # Форматирование объема бега для отображения
                    formatted_volume = format_weekly_volume(new_volume, str(total_distance))

                    # Создание кнопки для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])

                    # Отправка сообщения пользователю
                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {formatted_volume}.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.reply_text("❌ Не удалось отметить тренировку как отмененную.")

        except Exception as e:
            logging.error(f"Error marking training as canceled: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")

    # Обработка кнопки "Посмотреть текущий план"
    elif query.data == "view_plan":
        try:
            # Получаем последний план пользователя
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            if not plan:
                await query.message.reply_text("❌ У вас нет активного плана тренировок.")
                # Показываем главное меню снова
                await send_main_menu(update, context)
                return

            # Получаем выполненные и отмененные тренировки
            plan_id = plan['id']
            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)

            # Отправляем общую информацию о плане
            await query.message.reply_text(
                f"✅ Ваш персонализированный план тренировок:\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )

            # После показа плана восстанавливаем главное меню
            await send_main_menu(update, context, "Что еще вы хотите сделать?")

            # Отправляем каждый день тренировки с соответствующими кнопками
            # Проверяем структуру данных плана и выбираем правильное поле
            training_days = []
            if 'training_days' in plan:
                training_days = plan['training_days']
            elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                training_days = plan['plan_data']['training_days']

            logging.info(f"План для пользователя: {db_user_id}, структура: {plan.keys()}")
            logging.info(f"Найдено дней тренировок: {len(training_days)}")

            for idx, day in enumerate(training_days):
                training_day_num = idx + 1

                # Проверяем, выполнена ли тренировка
                day_completed = training_day_num in completed_days
                day_canceled = training_day_num in canceled_days

                # Используем функцию форматирования для согласованного вида
                day_message = format_training_day(day, training_day_num)
                
                # Формируем сообщение в зависимости от статуса
                if day_completed:
                    # Добавляем отметку о выполнении
                    day_message = "✅ " + day_message.strip() + " - ВЫПОЛНЕНО"
                    await query.message.reply_text(day_message, parse_mode='Markdown')
                elif day_canceled:
                    # Добавляем отметку об отмене
                    day_message = "❌ " + day_message.strip() + " - ОТМЕНЕНО"
                    await query.message.reply_text(day_message, parse_mode='Markdown')
                else:
                    # Дни без статуса остаются как есть

                    # Добавляем кнопки для действий
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                    ])

                    await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        except Exception as e:
            logging.error(f"Error viewing training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при просмотре плана тренировок.")

    # Обработка кнопки "Создать новый план"
    elif query.data == "new_plan":
        try:
            logging.info(f"Пользователь {telegram_id} (ID: {db_user_id}) запросил создание нового плана")

            # Проверяем статус оплаты - в расширенном варианте с детальным логированием
            logging.info(f"Проверяем статус оплаты для пользователя {telegram_id} (ID: {db_user_id})")
            payment_status = DBManager.get_payment_status(db_user_id)
            logging.info(f"Статус оплаты: {payment_status}")

            if not payment_status or not payment_status.get('payment_agreed', False):
                logging.warning(f"Пользователь {telegram_id} (ID: {db_user_id}) не имеет подтвержденного статуса оплаты")
                # Предлагаем оплату
                reply_markup = ReplyKeyboardMarkup(
                    [
                        ['Да, буду платить 500 рублей в месяц'],
                        ['Нет. Я и так МАШИНА Ой БОЙ!']
                    ],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )

                await query.message.reply_text(
                    "Для доступа к функции создания плана тренировок необходимо оформить подписку. " +
                    "Бот стоит 500 рублей в месяц с гарантией добавления новых фичей и легкой отменой!",
                    reply_markup=reply_markup
                )

                # Сохраняем состояние - ожидаем ответа на вопрос об оплате
                context.user_data['awaiting_payment_confirmation'] = True
                return
            else:
                logging.info(f"Пользователь {telegram_id} (ID: {db_user_id}) имеет подтвержденный статус оплаты")

                # Проверяем срок действия подписки
                if not DBManager.check_active_subscription(db_user_id):
                    logging.warning(f"Подписка пользователя {telegram_id} (ID: {db_user_id}) истекла")
                    # Предлагаем оплату снова
                    reply_markup = ReplyKeyboardMarkup(
                        [
                            ['Да, буду платить 500 рублей в месяц'],
                            ['Нет. Я и так МАШИНА Ой БОЙ!']
                        ],
                        one_time_keyboard=True,
                        resize_keyboard=True
                    )

                    await query.message.reply_text(
                        "Ваша подписка истекла. Для продолжения использования функции создания плана тренировок необходимо продлить подписку. " +
                        "Бот стоит 500 рублей в месяц с гарантией добавления новых фичей и легкой отменой!",
                        reply_markup=reply_markup
                    )

                    # Сохраняем состояние - ожидаем ответа на вопрос об оплате
                    context.user_data['awaiting_payment_confirmation'] = True
                    return

            # Получаем профиль пользователя
            logging.info(f"Получаем профиль для пользователя {telegram_id} (ID: {db_user_id})")
            profile = DBManager.get_runner_profile(db_user_id)
            logging.info(f"Профиль пользователя: {profile}")

            if not profile:
                logging.warning(f"Профиль для пользователя {telegram_id} (ID: {db_user_id}) не найден")
                # Инициируем сбор данных о пользователе
                await query.message.reply_text(
                    "Для создания персонализированного плана тренировок мне нужно собрать некоторую информацию о вас. "
                    "Давайте начнем с основных данных."
                )

                # Создаем и запускаем обработчик диалога
                conversation = RunnerProfileConversation()
                conversation_handler = conversation.get_conversation_handler()
                context.application.add_handler(conversation_handler)

                # Запускаем диалог
                await conversation.start(update, context)
                return

            # Устанавливаем флаг, что план уже создается, чтобы избежать дублирования
            user_data = context.user_data
            if user_data.get('is_generating_plan', False):
                logging.info(f"План уже создается для пользователя {telegram_id}. Пропускаем повторный запрос.")
                # Показываем главное меню снова
                await send_main_menu(update, context, "В данный момент идет создание плана. Выберите другое действие:")
                return

            # Устанавливаем флаг, что план создается
            user_data['is_generating_plan'] = True
            logging.info(f"Установлен флаг is_generating_plan для пользователя {telegram_id}")

            try:
                # Получаем сообщение о подготовке нового плана
                logging.info(f"Отправляем сообщение о подготовке плана пользователю {telegram_id}")
                with open("attached_assets/котик.jpeg", "rb") as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption="⏳ Генерирую новый персонализированный план тренировок с учетом вашего обновленного профиля. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                    )

                # Генерируем новый план по обновленному профилю
                logging.info(f"Начинаем генерацию плана для пользователя {telegram_id} с профилем: {profile}")
                try:
                    try:
                        # Пробуем использовать новый MCP-инструмент через адаптер
                        from agent.adapter import AgentAdapter
                        agent_adapter = AgentAdapter()
                        plan = agent_adapter.generate_training_plan(profile)
                        logging.info(f"План для пользователя {telegram_id} успешно создан через MCP-инструмент")
                    except Exception as mcp_error:
                        logging.error(f"Ошибка при использовании MCP-инструмента для пользователя {telegram_id}: {mcp_error}")
                        # В случае ошибки возвращаемся к старому методу
                        openai_service = OpenAIService()
                        plan = openai_service.generate_training_plan(profile)
                        logging.info(f"План для пользователя {telegram_id} создан через оригинальный OpenAIService после ошибки MCP")
                except Exception as openai_error:
                    logging.error(f"Ошибка при генерации плана через OpenAI для пользователя {telegram_id}: {openai_error}")
                    await query.message.reply_text(
                        "❌ Произошла ошибка при генерации плана. Возможно, проблема с OpenAI API. Пожалуйста, попробуйте позже."
                    )
                    user_data['is_generating_plan'] = False
                    return

                # Сохраняем план в базу данных
                logging.info(f"Сохраняем план в базу данных для пользователя {telegram_id}")
                plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

                if not plan_id:
                    logging.error(f"Не удалось сохранить план в базу данных для пользователя {telegram_id}")
                    await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                    user_data['is_generating_plan'] = False
                    return

                # Отправляем общую информацию о плане
                await query.message.reply_text(
                    f"✅ Ваш персонализированный план тренировок готов!\n\n"
                    f"*{plan['plan_name']}*\n\n"
                    f"{plan['plan_description']}",
                    parse_mode='Markdown'
                )

                # Отправляем каждый день тренировки с соответствующими кнопками
                for idx, day in enumerate(plan['training_days']):
                    training_day_num = idx + 1
                    day_message = format_training_day(day, training_day_num)

                    # Создаем кнопки для действий
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                    ])

                    await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)


                # Отправляем приглашение в чат БЕТА тестеров
                await query.message.reply_text("Если есть желание и время заходите в чатик БЕТА тестеров https://t.me/+oiEFpRKHRPA3ZDA6")
                # Показываем главное меню после генерации плана
                await send_main_menu(update, context, "Ваш план создан. Что еще вы хотите сделать?")
            finally:
                # Снимаем флаг генерации плана, даже если произошла ошибка
                user_data['is_generating_plan'] = False

        except Exception as e:
            logging.error(f"Error creating new training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при создании нового плана тренировок.")
            # Сбрасываем флаг генерации плана в случае ошибки
            context.user_data['is_generating_plan'] = False

    # Обработка кнопки "Подготовить план тренировок"
    elif query.data == "generate_plan":
        try:
            # Получаем данные пользователя
            telegram_id = update.effective_user.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name

            # Пытаемся добавить/обновить пользователя и получить ID
            db_user_id = DBManager.add_user(telegram_id, username, first_name, last_name)

            if not db_user_id:
                await query.message.reply_text("❌ Произошла ошибка при регистрации пользователя.")
                return

            # Проверяем, есть ли у пользователя профиль бегуна
            profile = DBManager.get_runner_profile(db_user_id)

            if not profile:
                # У пользователя нет профиля, предлагаем создать
                await query.message.reply_text(
                    "⚠️ У вас еще нет профиля бегуна. Давайте создадим его!\n\n"
                    "Для начала сбора данных, введите /plan"
                )
                return

            # Определяем, нужно ли предлагать создание нового плана
            # После обновления профиля всегда предлагаем создать новый план
            if context.user_data.get('profile_updated', False):
                # Профиль был обновлен, предлагаем создать новый план
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆕 Создать новый план", callback_data="new_plan")]
                ])

                await query.message.reply_text(
                    "Ваш профиль был обновлен! Вы можете создать новый персонализированный план тренировок с учетом этих изменений.",
                    reply_markup=keyboard
                )

                # Сбрасываем флаг обновления профиля
                context.user_data['profile_updated'] = False
                return

            # Проверяем, есть ли у пользователя уже существующий план тренировок
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            if plan:
                # У пользователя уже есть план, спрашиваем, что он хочет сделать
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👁️ Посмотреть текущий план", callback_data="view_plan")],
                    [InlineKeyboardButton("🆕 Создать новый план", callback_data="new_plan")]
                ])

                await query.message.reply_text(
                    "У вас уже есть план тренировок. Что вы хотите сделать?",
                    reply_markup=keyboard
                )
                return

            # Устанавливаем флаг, что план уже создается, чтобы избежать дублирования
            user_data = context.user_data
            if user_data.get('is_generating_plan', False):
                logging.info(f"План уже создается для пользователя {telegram_id}. Пропускаем повторный запрос.")
                return

            # Устанавливаем флаг, что план создается
            user_data['is_generating_plan'] = True

            try:
                # Генерируем новый план тренировок и отправляем сообщение с котиком
                with open("attached_assets/котик.jpeg", "rb") as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                    )

                # Генерируем план
                try:
                    # Пробуем использовать новый MCP-инструмент через адаптер
                    from agent.adapter import AgentAdapter
                    agent_adapter = AgentAdapter()
                    plan = agent_adapter.generate_training_plan(profile)
                    logging.info(f"План успешно создан через MCP-инструмент")
                except Exception as e:
                    logging.error(f"Ошибка при использовании MCP-инструмента: {e}")
                    # В случае ошибки возвращаемся к старому методу
                    openai_service = OpenAIService()
                    plan = openai_service.generate_training_plan(profile)
                    logging.info("План создан через оригинальный OpenAIService после ошибки MCP")

                # Сохраняем план в базу данных
                plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

                if not plan_id:
                    await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                    return

                # Отправляем общую информацию о плане
                await query.message.reply_text(
                    f"✅ Ваш персонализированный план тренировок готов!\n\n"
                    f"*{plan['plan_name']}*\n\n"
                    f"{plan['plan_description']}",
                    parse_mode='Markdown'
                )

                # Отправляем каждый день тренировки с кнопками действий
                for idx, day in enumerate(plan['training_days']):
                    training_day_num = idx + 1
                    day_message = format_training_day(day, training_day_num)

                    # Создаем кнопки "Выполнено" и "Отменить" для каждого дня тренировки
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                    ])

                    await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

                # Отправляем приглашение в чат БЕТА тестеров
                await query.message.reply_text("Если есть желание и время заходите в чатик БЕТА тестеров https://t.me/+oiEFpRKHRPA3ZDA6")

                # Показываем главное меню после генерации плана
                await send_main_menu(update, context, "Ваш план создан. Что еще вы хотите сделать?")
            finally:
                # Снимаем флаг генерации плана, даже если произошла ошибка
                user_data['is_generating_plan'] = False

        except Exception as e:
            logging.error(f"Error generating plan from button: {e}")
            await query.message.reply_text("❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже.")
            # Сбрасываем флаг генерации плана в случае ошибки
            context.user_data['is_generating_plan'] = False

    # Обработка кнопки "Ни один из этих дней" при анализе скриншота тренировки
    elif query.data == "none_match":
        try:
            # Пользователь указал, что ни один день тренировки не соответствует скриншоту
            await query.message.reply_text(
                "👍 Понятно! Я отмечу это как дополнительную тренировку вне вашего плана.\n\n"
                "Хорошая работа с дополнительной активностью! Продолжайте в том же духе! 💪"
            )
        except Exception as e:
            logging.error(f"Error handling none_match button: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса.")

    # Обработка кнопки показа истории тренировок
    elif query.data.startswith("show_history_"):
        # Формат: show_history_PLAN_ID
        try:
            _, _, plan_id = query.data.split('_')
            plan_id = int(plan_id)

            # Получаем информацию о плане тренировок
            plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)
            if not plan:
                await query.message.reply_text("❌ Не удалось найти план тренировок.")
                return

            # Получаем выполненные и отмененные тренировки
            completed = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)

            # Отправляем заголовок истории тренировок
            await query.message.reply_text(
                "📜 *История тренировок:*",
                parse_mode='Markdown'
            )

            # Проверяем, есть ли выполненные тренировки
            if completed:
                await query.message.reply_text(
                    "✅ *Выполненные тренировки:*",
                    parse_mode='Markdown'
                )

                # Отправляем информацию о выполненных тренировках
                for day_num in sorted(completed):
                    # Определяем день тренировки
                    day_idx = day_num - 1

                    # Определяем структуру плана
                    training_days = []
                    if 'training_days' in plan:
                        training_days = plan['training_days']
                    elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                        training_days = plan['plan_data']['training_days']

                    if day_idx < 0 or day_idx >= len(training_days):
                        continue

                    day = training_days[day_idx]

                    # Определяем тип тренировки
                    training_type = day.get('training_type') or day.get('type', 'Не указан')

                    # Используем функцию форматирования для согласованного вида
                    day_message = format_training_day(day, day_num)
                    # Добавляем иконку статуса в начало сообщения
                    training_message = "✅ " + day_message.strip()

                    await query.message.reply_text(
                        training_message,
                        parse_mode='Markdown'
                    )

            # Проверяем, есть ли отмененные тренировки
            if canceled:
                await query.message.reply_text(
                    "❌ *Отмененные тренировки:*",
                    parse_mode='Markdown'
                )

                # Отправляем информацию об отмененных тренировках
                for day_num in sorted(canceled):
                    # Определяем день тренировки
                    day_idx = day_num - 1

                    # Определяем структуру плана
                    training_days = []
                    if 'training_days' in plan:
                        training_days = plan['training_days']
                    elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                        training_days = plan['plan_data']['training_days']

                    if day_idx < 0 or day_idx >= len(training_days):
                        continue

                    day = training_days[day_idx]

                    # Определяем тип тренировки
                    training_type = day.get('training_type') or day.get('type', 'Не указан')

                    # Используем функцию форматирования для согласованного вида
                    day_message = format_training_day(day, day_num)
                    # Добавляем иконку статуса в начало сообщения
                    training_message = "❌ " + day_message.strip()

                    await query.message.reply_text(
                        training_message,
                        parse_mode='Markdown'
                    )

            # Если нет ни выполненных, ни отмененных тренировок
            if not completed and not canceled:
                await query.message.reply_text(
                    "ℹ️ У вас пока нет выполненных или отмененных тренировок в этом плане."
                )

        except Exception as e:
            logging.error(f"Ошибка при показе истории тренировок: {e}")
            await query.message.reply_text("❌ Произошла ошибка при показе истории тренировок.")

    # Обработка ручного сопоставления тренировки со скриншота
    elif query.data.startswith("manual_match_"):
        try:
            # Разбираем callback data: manual_match_{plan_id}_{day_num}_{workout_distance}
            parts = query.data.split('_')

            # Проверяем, правильный ли формат
            if len(parts) < 5:
                await query.message.reply_text("❌ Неверный формат callback_data для ручного сопоставления.")
                return

            # Извлекаем параметры
            plan_id = int(parts[2])
            day_num = int(parts[3])
            workout_distance = float(parts[4])

            # Получаем текущий план
            plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)
            if not plan:
                await query.message.reply_text("❌ Не удалось найти указанный план тренировок.")
                return

            # Проверяем структуру данных плана и выбираем правильное поле для training_days
            training_days = []
            if 'training_days' in plan:
                training_days = plan['training_days']
            elif 'plan_data' in plan and isinstance(plan['plan_data'], dict) and 'training_days' in plan['plan_data']:
                training_days = plan['plan_data']['training_days']

            # Проверяем, не выходит ли day_num за пределы списка
            if day_num <= 0 or day_num > len(training_days):
                await query.message.reply_text("❌ Указан неверный номер дня тренировки.")
                return

            # Получаем данные о дне тренировки
            day_idx = day_num - 1
            matched_day = training_days[day_idx]

            # Получаем список обработанных дней
            completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
            processed_days = completed_days + canceled_days

            # Проверяем, не обработан ли уже этот день
            if day_num in processed_days:
                await query.message.reply_text(
                    f"⚠️ Тренировка за *{matched_day['date']}* уже отмечена как выполненная или отмененная.",
                    parse_mode='Markdown'
                )
                return

            # Отмечаем тренировку как выполненную
            success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, day_num)

            if success:
                # Обновляем еженедельный объем в профиле пользователя
                DBManager.update_weekly_volume(db_user_id, workout_distance)

                # Извлекаем запланированную дистанцию
                planned_distance = 0
                try:
                    # Извлекаем числовое значение из строки с дистанцией (напр., "5 км" -> 5)
                    import re
                    distance_match = re.search(r'(\d+(\.\d+)?)', matched_day['distance'])
                    if distance_match:
                        planned_distance = float(distance_match.group(1))
                        logging.info(f"Успешно извлечена плановая дистанция: {planned_distance} км из '{matched_day['distance']}'")
                    else:
                        logging.warning(f"Не удалось извлечь числовое значение дистанции из строки: '{matched_day['distance']}'")
                except Exception as e:
                    logging.warning(f"Error extracting planned distance: {e}")

                # Проверяем, значительно ли отличается фактическая дистанция от запланированной
                diff_percent = 0
                if planned_distance > 0 and workout_distance > 0:
                    diff_percent = abs(workout_distance - planned_distance) / planned_distance * 100
                    logging.info(f"Вычислена разница между фактической ({workout_distance} км) и плановой ({planned_distance} км) дистанцией: {diff_percent:.2f}%")

                # Получаем форматированную информацию о дне тренировки
                day_message = format_training_day(matched_day, day_num)
                
                # Формируем сообщение о сопоставлении
                training_completion_msg = (
                    f"✅ *Тренировка успешно сопоставлена с выбранным днем!*\n\n"
                    f"Плановая дистанция: {matched_day['distance']}\n"
                    f"Фактическая дистанция: {workout_distance} км\n\n"
                )

                # Если разница более 20%
                if diff_percent > 20 and training_days:
                    # Добавляем сообщение о значительной разнице
                    if workout_distance > planned_distance:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% больше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план недостаточно интенсивен для вас.\n\n"
                        )
                    else:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% меньше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план слишком интенсивен для вас.\n\n"
                        )

                    # Предлагаем скорректировать план
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Скорректировать план", callback_data=f"adjust_plan_{plan_id}_{day_num}_{workout_distance}_{planned_distance}")]
                    ])

                    training_completion_msg += "Хотите скорректировать оставшиеся тренировки с учетом вашего фактического выполнения?"

                    await query.message.edit_text(
                        training_completion_msg,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                else:
                    # Нет значительной разницы или нет оставшихся дней
                    training_completion_msg += f"Тренировка отмечена как выполненная! 👍"

                    await query.message.edit_text(
                        training_completion_msg,
                        parse_mode='Markdown'
                    )

                # Проверяем, все ли тренировки теперь выполнены
                all_processed_days = TrainingPlanManager.get_all_processed_trainings(db_user_id, plan_id)
                if len(all_processed_days) == len(training_days):
                    # Вычисляем общую пройденную дистанцию
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

                    # Создаем кнопку для продолжения тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])

                    await query.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await query.message.edit_text(
                    "❌ Не удалось отметить тренировку как выполненную. Пожалуйста, попробуйте позже.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logging.error(f"Error handling manual match: {e}")
            await query.message.edit_text(
                "❌ Произошла ошибка при обработке ручного сопоставления. Пожалуйста, попробуйте позже."
            )

    # Обработка кнопки "Это дополнительная тренировка"
    elif query.data == "extra_training":
        await query.message.edit_text(
            "👍 Принято! Эта тренировка засчитана как дополнительная и не связана с текущим планом. "
            "Продолжайте следовать своему регулярному плану тренировок!"
        )

    # Обработка кнопки корректировки плана
    elif query.data.startswith("adjust_plan_"):
        try:
            # Разбираем callback data: adjust_plan_{plan_id}_{day_num}_{actual_distance}_{planned_distance}
            parts = query.data.split('_')

            # Проверяем, правильный ли формат
            if len(parts) < 6:
                await query.message.reply_text("❌ Неверный формат callback_data для корректировки плана.")
                return

            # Извлекаем параметры
            plan_id = int(parts[2])
            day_num = int(parts[3])
            actual_distance = float(parts[4])
            planned_distance = float(parts[5])

            # Получаем профиль бегуна
            runner_profile = DBManager.get_runner_profile(db_user_id)
            if not runner_profile:
                await query.message.reply_text("❌ Не удалось получить профиль бегуна.")
                return

            # Получаем текущий план
            current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
            if not current_plan or current_plan['id'] != plan_id:
                await query.message.reply_text("❌ Не удалось найти указанный план тренировок.")
                return

            # Отправляем сообщение о начале корректировки
            await query.message.reply_text(
                "🔄 Корректирую ваш план тренировок с учетом фактического выполнения...\n"
                "Это может занять некоторое время."
            )

            # Сначала пробуем использовать MCP-адаптер для корректировки плана
            try:
                logging.info("Инициализация AgentAdapter для корректировки плана")
                from agent.adapter import AgentAdapter
                agent_adapter = AgentAdapter()
                
                logging.info(f"Вызов agent_adapter для корректировки плана: день={day_num}, план/факт={planned_distance}/{actual_distance}")
                # Теперь у нас есть реализация метода корректировки в AgentAdapter
                adjusted_plan = agent_adapter.adjust_training_plan(
                    runner_profile,
                    current_plan['plan_data'],
                    day_num,
                    planned_distance,
                    actual_distance
                )
                logging.info("План успешно скорректирован через MCP-инструмент")
            except Exception as adapter_error:
                # Если произошла ошибка, используем стандартный OpenAIService
                logging.error(f"Ошибка при использовании AgentAdapter для корректировки: {adapter_error}")
                openai_service = OpenAIService()
                adjusted_plan = openai_service.adjust_training_plan(
                    runner_profile,
                    current_plan['plan_data'],
                    day_num,
                    planned_distance,
                    actual_distance
                )
                logging.info("План скорректирован через OpenAIService после ошибки адаптера")

            if not adjusted_plan:
                await query.message.reply_text("❌ Не удалось скорректировать план. Пожалуйста, попробуйте позже.")
                return

            # Обновляем план в базе данных
            success = TrainingPlanManager.update_training_plan(db_user_id, plan_id, adjusted_plan)

            if not success:
                await query.message.reply_text("❌ Не удалось сохранить скорректированный план.")
                return

            # Получаем обновленный план
            updated_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            # Отправляем информацию о скорректированном плане
            await query.message.reply_text(
                f"✅ Ваш план тренировок успешно скорректирован!\n\n"
                f"*{updated_plan['plan_data']['plan_name']}*\n\n"
                f"{updated_plan['plan_data']['plan_description']}\n\n"
                f"📋 Вот оставшиеся дни вашего скорректированного плана:",
                parse_mode='Markdown'
            )

            # Получаем обработанные тренировки
            completed = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
            canceled = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)

            # Отправляем только оставшиеся (не выполненные и не отмененные) дни тренировок
            for idx, day in enumerate(updated_plan['plan_data']['training_days']):
                training_day_num = idx + 1

                # Пропускаем уже обработанные дни
                if training_day_num in completed or training_day_num in canceled:
                    continue

                # Используем функцию форматирования тренировочного дня для согласованного вида
                day_message = format_training_day(day, training_day_num)

                # Создаем кнопки "Выполнено" и "Отменить" для каждого дня тренировки
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{plan_id}_{training_day_num}")]
                ])

                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        except Exception as e:
            logging.error(f"Error adjusting plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при корректировке плана.")

    # Обработка кнопки "Продолжить тренировки"
    elif query.data.startswith('continue_plan_'):
        # Формат: continue_plan_PLAN_ID
        try:
            _, _, plan_id = query.data.split('_')
            plan_id = int(plan_id)

            # Получение данных пользователя
            telegram_id = update.effective_user.id
            username = update.effective_user.username

            # Логируем информацию о пользователе для отладки
            logging.info(f"Пользователь: {username} (ID: {telegram_id}), db_user_id: {db_user_id}")
            logging.info(f"Пытаемся продолжить план {plan_id}")

            # Если профиль не найден, попробуем пересоздать его
            profile = DBManager.get_runner_profile(db_user_id)

            if not profile:
                logging.warning(f"Профиль бегуна для пользователя {username} (ID: {telegram_id}) не найден")

                # Проверяем, возможно нужно заново получить db_user_id
                db_user_id_check = DBManager.get_user_id(telegram_id)
                logging.info(f"Проверка db_user_id: {db_user_id_check}")

                if db_user_id_check and db_user_id_check != db_user_id:
                    db_user_id = db_user_id_check
                    profile = DBManager.get_runner_profile(db_user_id)

                # Если профиль всё еще не найден, попробуем создать профиль по умолчанию
                if not profile:
                    logging.info(f"Creating default profile for user: {username} (ID: {telegram_id})")
                    try:
                        # Создание профиля по умолчанию
                        profile = DBManager.create_default_runner_profile(db_user_id)

                        if profile:
                            logging.info(f"Default profile created successfully for {username}")
                            await query.message.reply_text(
                                "⚠️ Нам не удалось найти ваш оригинальный профиль, но мы создали для вас базовый профиль, "
                                "чтобы продолжить тренировки.\n\n"
                                "Вы всегда можете обновить свои данные через команду /plan"
                            )
                        else:
                            # Если не удалось создать профиль, предлагаем пользователю создать его самостоятельно
                            logging.warning(f"Failed to create default profile for {username}")
                            await query.message.reply_text(
                                "❌ Не удалось найти профиль бегуна. Похоже, данные вашего профиля были потеряны.\n\n"
                                "Пожалуйста, создайте новый профиль с помощью команды /plan"
                            )
                            return
                    except Exception as e:
                        logging.error(f"Error creating default profile: {e}")
                        await query.message.reply_text(
                            "❌ Произошла ошибка при попытке восстановить ваш профиль.\n\n"
                            "Пожалуйста, создайте новый профиль с помощью команды /plan"
                        )
                        return

            # Получаем план по ID или последний план
            try:
                # Сначала пробуем получить план по ID из callback_data
                current_plan = TrainingPlanManager.get_training_plan(db_user_id, plan_id)

                # Если не нашли план по ID, попробуем использовать последний план
                if not current_plan:
                    current_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
                    logging.info(f"План по ID {plan_id} не найден, пробуем использовать последний план: {current_plan['id'] if current_plan else 'Нет плана'}")

                # Если план все равно не найден, сообщаем пользователю
                if not current_plan:
                    await query.message.reply_text("❌ Не удалось найти план тренировок. Пожалуйста, создайте новый план с помощью команды /plan")
                    return
            except Exception as e:
                logging.error(f"Ошибка при получении плана тренировок: {e}")
                await query.message.reply_text("❌ Произошла ошибка при получении плана тренировок. Пожалуйста, попробуйте позже.")
                return

            # Расчет общего пройденного расстояния
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

            # Сообщаем пользователю о начале генерации нового плана
            with open("attached_assets/котик.jpeg", "rb") as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=f"⏳ Генерирую продолжение плана тренировок с учетом вашего прогресса ({total_distance:.1f} км). Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                )

            # Получаем сервис OpenAI и генерируем продолжение плана
            try:
                # Сначала пробуем использовать MCP-инструмент через адаптер
                try:
                    logging.info("Инициализация AgentAdapter для продолжения плана")
                    from agent.adapter import AgentAdapter
                    agent_adapter = AgentAdapter()
                    
                    logging.info(f"Вызов agent_adapter.generate_training_plan_continuation с параметрами: profile_id={profile['id']}, total_distance={total_distance}")
                    new_plan = agent_adapter.generate_training_plan_continuation(profile, total_distance, current_plan['plan_data'])
                    logging.info(f"Получен новый план через MCP-инструмент: {new_plan.get('plan_name', 'Неизвестный план')}")
                except Exception as adapter_error:
                    # Если произошла ошибка с адаптером, используем старый сервис
                    logging.error(f"Ошибка при использовании AgentAdapter: {adapter_error}")
                    logging.info("Переключение на OpenAIService для продолжения плана")
                    
                    openai_service = OpenAIService()
                    logging.info(f"Вызов openai_service.generate_training_plan_continuation с параметрами: profile_id={profile['id']}, total_distance={total_distance}")
                    new_plan = openai_service.generate_training_plan_continuation(profile, total_distance, current_plan['plan_data'])
                    logging.info(f"Получен новый план через OpenAIService: {new_plan.get('plan_name', 'Неизвестный план')}")

                # Сохраняем новый план в базу данных
                logging.info(f"Сохранение нового плана в БД для пользователя {db_user_id}")
                new_plan_id = TrainingPlanManager.save_training_plan(db_user_id, new_plan)
                logging.info(f"Новый план сохранен с ID: {new_plan_id}")
            except Exception as e:
                logging.error(f"Ошибка при генерации или сохранении плана: {e}")
                await query.message.reply_text(
                    "❌ Произошла ошибка при генерации нового плана тренировок. Пожалуйста, попробуйте позже."
                )
                return

            if not new_plan_id:
                await query.message.reply_text("❌ Произошла ошибка при сохранении плана. Пожалуйста, попробуйте позже.")
                return

            # Отправляем общую информацию о плане
            await query.message.reply_text(
                f"✅ Ваш новый план тренировок готов!\n\n"
                f"*{new_plan['plan_name']}*\n\n"
                f"{new_plan['plan_description']}",
                parse_mode='Markdown'
            )

            # Показываем главное меню после генерации нового плана
            await send_main_menu(update, context, "Что еще вы хотите сделать?")

            # Отправляем каждый день тренировки с соответствующими кнопками
            for idx, day in enumerate(new_plan['training_days']):
                training_day_num = idx + 1
                day_message = format_training_day(day, training_day_num)

                # Создаем кнопки для действий
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Отметить как выполненное", callback_data=f"complete_{new_plan_id}_{training_day_num}")],
                    [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{new_plan_id}_{training_day_num}")]
                ])

                await query.message.reply_text(day_message, parse_mode='Markdown', reply_markup=keyboard)

        except Exception as e:
            logging.error(f"Error continuing training plan: {e}")
            await query.message.reply_text("❌ Произошла ошибка при создании продолжения плана тренировок.")

async def handle_photo(update, context):
    """Handler for photo messages to analyze workout screenshots."""
    try:
        # Get user information
        telegram_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        first_name = update.effective_user.first_name or "Unknown"

        # Log the photo reception
        logging.info(f"Received photo from {username} (ID: {telegram_id})")

        # Check if user exists in database
        db_user_id = DBManager.get_user_id(telegram_id)
        if not db_user_id:
            # User not found, prompt to create a profile
            await update.message.reply_text(
                "⚠️ Для анализа тренировки сначала нужно создать профиль бегуна. "
                "Используйте команду /plan для создания профиля."
            )
            return

        # Check if user has an active training plan
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        if not plan:
            await update.message.reply_text(
                "❌ У вас еще нет плана тренировок. Используйте команду /plan для его создания."
            )
            return

        # Send processing message
        processing_message = await update.message.reply_text(
            "🔍 Анализирую ваш скриншот тренировки... Это может занять некоторое время."
        )

        # Get photo with best quality
        photo = update.message.photo[-1]

        # Download the photo
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()

        # Analyze the screenshot
        analyzer = ImageAnalyzer()
        workout_data = analyzer.analyze_workout_screenshot(photo_bytes)

        # Log the analysis results in detail
        logging.info(f"Детальный анализ скриншота тренировки: {workout_data}")

        # Отдельно логируем важные поля для отладки
        if "дистанция_км" in workout_data:
            logging.info(f"Обнаружена дистанция: {workout_data['дистанция_км']} км")
        else:
            logging.warning("Дистанция не обнаружена в скриншоте!")

        if "дата" in workout_data:
            logging.info(f"Обнаружена дата тренировки: {workout_data['дата']}")
        else:
            logging.warning("Дата не обнаружена в скриншоте!")

        # Check if analysis was successful
        if 'error' in workout_data:
            await update.message.reply_text(
                f"❌ Не удалось проанализировать скриншот: {workout_data['error']}\n\n"
                "Пожалуйста, убедитесь, что скриншот содержит информацию о тренировке и попробуйте снова."
            )
            return

        # Get training plan data
        plan_id = plan['id']
        training_days = plan['plan_data']['training_days']

        # Get processed training days
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days

        # Check if this is a running workout or another type of workout
        workout_type = workout_data.get("тип_тренировки", "").lower()

        # Check common running workout types in Russian and English
        running_types = ["бег", "пробежка", "run", "running", "jogging", "бег трусцой"]
        is_running_workout = any(run_type in workout_type for run_type in running_types) if workout_type else True

        if workout_type and not is_running_workout:
            # Create buttons for marking training as completed manually
            buttons = []
            for idx, day in enumerate(training_days):
                day_num = idx + 1
                if day_num not in processed_days:
                    buttons.append([InlineKeyboardButton(
                        f"День {day_num}: {day['day']} ({day['date']}) - {day['distance']}",
                        callback_data=f"complete_{plan_id}_{day_num}"
                    )])

            # Only add buttons if we have some unprocessed days
            if buttons:
                keyboard = InlineKeyboardMarkup(buttons)

                await update.message.reply_text(
                    f"⚠️ Обнаружена тренировка типа *{workout_type}*!\n\n"
                    f"В данный момент я могу обрабатывать только беговые тренировки. "
                    f"Поддержка других типов тренировок (плавание, велосипед, силовые и т.д.) "
                    f"будет добавлена в ближайшее время.\n\n"
                    f"Вы можете загрузить скриншот беговой тренировки или выбрать день тренировки, "
                    f"который хотите отметить как выполненный:",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Обнаружена тренировка типа *{workout_type}*!\n\n"
                    f"В данный момент я могу обрабатывать только беговые тренировки. "
                    f"Поддержка других типов тренировок (плавание, велосипед, силовые и т.д.) "
                    f"будет добавлена в ближайшее время.\n\n"
                    f"Пожалуйста, загрузите скриншот беговой тренировки.",
                    parse_mode='Markdown'
                )
            return

        # Получаем данные даты из скриншота для правильного сопоставления
        workout_date_str = workout_data.get("дата", "")
        # Преобразуем дату "DD.MM.YYYY" в объект datetime для сравнения
        workout_date_obj = None
        if workout_date_str:
            try:
                # Пробуем стандартный российский формат
                workout_date_obj = datetime.strptime(workout_date_str, "%d.%m.%Y")
                logging.info(f"Получена дата тренировки из скриншота: {workout_date_obj.strftime('%Y-%m-%d')}")
            except ValueError:
                # Пробуем другие форматы (например, американский "April 27, 2025")
                try:
                    # Извлекаем дату из строки в формате "4/27/25 - 11:17 AM"
                    import re
                    date_match = re.search(r'(\d+)/(\d+)/(\d+)', workout_date_str)
                    if date_match:
                        month, day, year = map(int, date_match.groups())
                        # Предполагаем, что это 20xx год
                        if year < 100:
                            year += 2000
                        workout_date_obj = datetime(year, month, day)
                        logging.info(f"Получена дата тренировки из скриншота (альтернативный формат): {workout_date_obj.strftime('%Y-%m-%d')}")
                except Exception as e:
                    logging.warning(f"Не удалось распознать дату из '{workout_date_str}': {e}")

        # Устанавливаем принудительное сопоставление с днем из плана по дате, если дата есть и соответствует одному из дней плана
        forced_match_idx = None
        if workout_date_obj:
            for i, day in enumerate(training_days):
                day_date_str = day.get('date', '')
                try:
                    # Преобразуем дату из плана "DD.MM.YYYY" в объект datetime
                    day_date_obj = datetime.strptime(day_date_str, "%d.%m.%Y")

                    # Если даты совпадают, устанавливаем принудительное сопоставление
                    if day_date_obj.date() == workout_date_obj.date():
                        forced_match_idx = i
                        logging.info(f"Принудительное сопоставление по дате: День {i+1} ({day_date_str})")
                        break
                except ValueError:
                    logging.warning(f"Не удалось преобразовать дату '{day_date_str}' из плана.")

        # Если есть принудительное сопоставление по дате, используем его, иначе используем алгоритм
        if forced_match_idx is not None:
            matching_day_idx = forced_match_idx
            matching_score = 10  # Высокий балл для сопоставления по дате
            logging.info(f"Используется принудительное сопоставление по дате: День {matching_day_idx+1}")
        else:
            # Используем стандартный алгоритм сопоставления, если не удалось сопоставить по дате
            matching_day_idx, matching_score = analyzer.find_matching_training(training_days, workout_data)

        # Extract workout details for display
        workout_date = workout_data.get("дата", "Неизвестно")
        workout_distance = workout_data.get("дистанция_км", "Неизвестно")
        workout_time = workout_data.get("длительность", "Неизвестно")
        workout_pace = workout_data.get("темп", "Неизвестно")
        workout_app = workout_data.get("название_приложения", "Неизвестно")

        # Create acknowledgment message
        ack_message = (
            f"✅ Информация о тренировке успешно получена!\n\n"
            f"Дата: *{workout_date}*\n"
            f"Дистанция: *{workout_distance} км*\n"
            f"Время: *{workout_time}*\n"
            f"Темп: *{workout_pace}*\n"
            f"Источник: *{workout_app}*\n\n"
        )

        # Если мы нашли подходящий день тренировки с высоким рейтингом
        if matching_day_idx is not None and matching_score >= 5:
            # Get the matched training day number (1-based index)
            matched_day_num = matching_day_idx + 1
            matched_day = training_days[matching_day_idx]

            logging.info(f"Автоматически сопоставлен день тренировки: День {matched_day_num} ({matched_day['day']} {matched_day['date']})")

            # Check if this training day is already processed
            if matched_day_num in processed_days:
                await update.message.reply_text(
                    f"{ack_message}⚠️ Тренировка за *{matched_day['date']}* уже отмечена как выполненная или отмененная.",
                    parse_mode='Markdown'
                )
                return

            # Mark training as completed
            success = TrainingPlanManager.mark_training_completed(db_user_id, plan_id, matched_day_num)

            if success:
                # Update weekly volume in profile (add completed distance)
                try:
                    distance_km = float(workout_distance)
                    DBManager.update_weekly_volume(db_user_id, distance_km)
                except (ValueError, TypeError):
                    logging.warning(f"Could not update weekly volume with distance: {workout_distance}")

                # Extract planned distance
                planned_distance = 0
                try:
                    # Extract numeric value from distance string (e.g., "5 км" -> 5)
                    import re
                    distance_match = re.search(r'(\d+(\.\d+)?)', matched_day['distance'])
                    if distance_match:
                        planned_distance = float(distance_match.group(1))
                        logging.info(f"Успешно извлечена плановая дистанция: {planned_distance} км из '{matched_day['distance']}'")
                    else:
                        logging.warning(f"Не удалось извлечь числовое значение дистанции из строки: '{matched_day['distance']}'")
                except Exception as e:
                    logging.warning(f"Error extracting planned distance: {e}")

                # Check if actual distance significantly differs from planned distance
                try:
                    actual_distance = float(workout_distance)
                    logging.info(f"Преобразована фактическая дистанция в число: {actual_distance} км")
                except ValueError as e:
                    logging.error(f"Ошибка преобразования фактической дистанции '{workout_distance}' в число: {e}")
                    actual_distance = 0

                diff_percent = 0
                if planned_distance > 0 and actual_distance > 0:
                    diff_percent = abs(actual_distance - planned_distance) / planned_distance * 100
                    logging.info(f"Вычислена разница между фактической ({actual_distance} км) и плановой ({planned_distance} км) дистанцией: {diff_percent:.2f}%")

                # Create the acknowledgment message
                training_completion_msg = (
                    f"{ack_message}🎉 Тренировка успешно сопоставлена с планом!\n\n"
                    f"День {matched_day_num}: {matched_day['day']} ({matched_day['date']})\n"
                    f"Тип: {matched_day['training_type']}\n"
                    f"Плановая дистанция: {matched_day['distance']}\n"
                    f"Фактическая дистанция: {workout_distance} км\n\n"
                )

                # Логируем текущее условие для определения ошибки
                logging.info(f"Проверка условия корректировки плана: diff_percent={diff_percent}, training_days_exists={bool(training_days)}, remaining_days={len(training_days) > matched_day_num}")

                # If difference is more than 20%
                # Проверяем, что: 
                # 1) разница больше 20%
                # 2) есть training_days
                # 3) проверяем остались ли дни в плане (для логики отображения кнопок)
                # Всегда предлагаем корректировку плана, если разница > 20%
                remaining_days = len([day_num for day_num in range(1, len(training_days) + 1) if day_num > matched_day_num and day_num not in processed_days])
                is_last_day = (matched_day_num == len(training_days))
                logging.info(f"Оставшиеся необработанные дни в плане: {remaining_days}, это последний день: {is_last_day}, разница в дистанциях: {diff_percent:.2f}%")

                if diff_percent > 20 and training_days:
                    # Add a message about the significant difference
                    if actual_distance > planned_distance:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% больше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план недостаточно интенсивен для вас.\n\n"
                        )
                    else:
                        training_completion_msg += (
                            f"⚠️ Ваша фактическая дистанция на {diff_percent:.1f}% меньше запланированной!\n"
                            f"Это может указывать на то, что ваш текущий план слишком интенсивен для вас.\n\n"
                        )

                    # Проверяем, является ли это последним днем плана
                    if is_last_day:
                        # Если это последний день плана, предлагаем создать новый план
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Создать новый план", callback_data=f"continue_plan_{plan_id}")]
                        ])

                        training_completion_msg += "Это последний день вашего плана. Хотите создать новый план с учетом ваших фактических результатов?"
                    else:
                        # Иначе предлагаем скорректировать существующий план
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("📝 Скорректировать план", callback_data=f"adjust_plan_{plan_id}_{matched_day_num}_{actual_distance}_{planned_distance}")]
                        ])

                        training_completion_msg += "Хотите скорректировать оставшиеся тренировки с учетом вашего фактического выполнения?"

                    await update.message.reply_text(
                        training_completion_msg,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                else:
                    # No significant difference or no remaining days
                    training_completion_msg += f"Тренировка отмечена как выполненная! 👍"

                    await update.message.reply_text(
                        training_completion_msg,
                        parse_mode='Markdown'
                    )

                # Check if all trainings are now completed
                all_processed_days = TrainingPlanManager.get_all_processed_trainings(db_user_id, plan_id)
                if len(all_processed_days) == len(training_days):
                    # Calculate total completed distance
                    total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)

                    # Create continue button
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
                    ])

                    await update.message.reply_text(
                        f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                        f"Вы пробежали в общей сложности {total_distance:.1f} км.\n\n"
                        f"Хотите продолжить тренировки с учетом вашего прогресса?",
                        reply_markup=keyboard
                    )
            else:
                await update.message.reply_text(
                    f"{ack_message}❌ Не удалось отметить тренировку как выполненную. Пожалуйста, попробуйте сделать это вручную через /pending.",
                    parse_mode='Markdown'
                )
        else:
            # Создаем кнопки для всех непомеченных дней тренировки, чтобы пользователь мог выбрать вручную
            buttons = []
            for idx, day in enumerate(training_days):
                day_num = idx + 1
                if day_num not in processed_days:
                    buttons.append([InlineKeyboardButton(
                        f"День {day_num}: {day['day']} ({day['date']}) - {day['distance']}",
                        callback_data=f"manual_match_{plan_id}_{day_num}_{workout_distance}"
                    )])

            # Добавляем кнопку "Это дополнительная тренировка"
            buttons.append([InlineKeyboardButton("🏃‍♂️ Это дополнительная тренировка", callback_data="extra_training")])

            keyboard = InlineKeyboardMarkup(buttons)

            await update.message.reply_text(
                f"{ack_message}❓ Не удалось автоматически сопоставить эту тренировку с вашим планом.\n\n"
                f"Пожалуйста, выберите день тренировки, который хотите отметить как выполненный:",
                parse_mode='Markdown',
                reply_markup=keyboard
            )

            # После отправки кнопок для ручного сопоставления показываем главное меню
            await send_main_menu(update, context, "Что еще вы хотите сделать?")

    except Exception as e:
        logging.error(f"Error handling photo: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при анализе фотографии. Пожалуйста, попробуйте позже или отметьте тренировку вручную через /pending."
        )

        # После обработки ошибки показываем главное меню
        await send_main_menu(update, context)


def setup_bot():
    """Configure and return the bot application."""
    # Create the Application object
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Create database tables if they don't exist
    create_tables()

    # Add command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", generate_plan_command))
    application.add_handler(CommandHandler("pending", pending_trainings_command))
    
    # Добавляем дополнительный обработчик для команды /start
    async def direct_start_command(update, context):
        """
        Прямой обработчик команды /start, который запускает создание профиля
        независимо от ConversationHandler
        """
        # Получаем объект RunnerProfileConversation
        conversation = RunnerProfileConversation()
        # Запускаем метод start из этого класса
        await conversation.start(update, context)
    
    # Регистрируем обработчик с высоким приоритетом
    application.add_handler(CommandHandler("start", direct_start_command), group=0)

    # Добавляем обработчик команды отмены
    async def cancel_command(update, context):
        """Handler for the /cancel command - cancels current conversation."""
        # Очищаем данные диалога
        context.user_data.clear()

        # Сначала отправляем сообщение об отмене без клавиатуры
        await update.message.reply_text(
            "❌ Операция отменена. Ваш профиль остался без изменений.",
            reply_markup=ReplyKeyboardRemove()
        )

        # Используем нашу новую функцию для показа главного меню
        await send_main_menu(update, context, "Что бы вы хотели сделать дальше?")

        return END

    application.add_handler(CommandHandler("cancel", cancel_command))

    # Этот обработчик команды теперь определен вне функции setup_bot

    application.add_handler(CommandHandler("update", update_profile_command))

    # Add conversation handlers for profile creation and update
    conversation = RunnerProfileConversation()
    conv_handlers = conversation.get_conversation_handler()

    # Если get_conversation_handler вернул список обработчиков, добавляем каждый отдельно
    # Используем группу 1, чтобы они имели более низкий приоритет, чем прямой обработчик /start
    if isinstance(conv_handlers, list):
        for handler in conv_handlers:
            application.add_handler(handler, group=1)
    else:
        # Если вернул один обработчик, добавляем его напрямую
        application.add_handler(conv_handlers, group=1)

    # Add photo handler for analyzing workout screenshots
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Add text message handler for button responses
    async def text_message_handler(update, context):
        """Обработчик текстовых сообщений от пользователя."""
        # Пропускаем обработку команд, включая /start
        if update.message.text.startswith('/'):
            return
            
        text = update.message.text.strip()
        user = update.effective_user
        telegram_id = user.id

        # Получаем ID пользователя в БД
        db_user_id = DBManager.get_user_id(telegram_id)

        if not db_user_id:
            await update.message.reply_text(
                "Пожалуйста, используйте команду /start, чтобы начать работу с ботом."
            )
            return

        # Проверяем, ожидает ли пользователь подтверждения оплаты
        if context.user_data.get('awaiting_payment_confirmation', False):
            # Обрабатываем ответ на вопрос об оплате
            if text == "Да, буду платить 500 рублей в месяц":
                # Импортируем функцию для отображения главного меню
                
                # Сбрасываем флаг ожидания оплаты
                context.user_data['awaiting_payment_confirmation'] = False

                # Отмечаем согласие на оплату
                context.user_data['payment_agreed'] = True

                # Сохраняем статус оплаты в базе данных
                DBManager.save_payment_status(db_user_id, True)

                # Отправляем сообщение об успешной подписке
                await update.message.reply_text(
                    "🎉 Отлично! Ваша подписка активирована. Теперь вы можете получить "
                    "персонализированный план тренировок, основанный на вашем профиле."
                )

                # Отправляем главное меню
                await send_main_menu(update, context, 
                    "Выберите 'Создать план тренировок', чтобы сгенерировать ваш персональный план."
                )
                return

            elif text == "Нет. Я и так МАШИНА Ой БОЙ!":
                # Сбрасываем флаг ожидания оплаты
                context.user_data['awaiting_payment_confirmation'] = False

                # Отмечаем отказ от оплаты
                context.user_data['payment_agreed'] = False

                # Сохраняем статус оплаты в базе данных
                DBManager.save_payment_status(db_user_id, False)

                # Отправляем сообщение о будущей бесплатной версии
                await update.message.reply_text(
                    "Очень жаль, но я скоро сделаю простую бесплатную версию и пришлю ее тебе",
                    reply_markup=ReplyKeyboardRemove()
                )
                return

        # Обрабатываем различные текстовые команды от кнопок
        if text == "👁️ Посмотреть текущий план":
            # Перенаправляем на обработку команды просмотра плана
            plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            if not plan:
                await update.message.reply_text(
                    "У вас еще нет плана тренировок. Создайте его командой /plan"
                )
                return

            # Получаем обработанные тренировки
            completed = TrainingPlanManager.get_completed_trainings(db_user_id, plan['id'])
            canceled = TrainingPlanManager.get_canceled_trainings(db_user_id, plan['id'])
            processed_days = completed + canceled  # Все обработанные дни

            # Отправляем общую информацию о плане
            await update.message.reply_text(
                f"✅ Ваш персонализированный план тренировок:\n\n"
                f"*{plan['plan_name']}*\n\n"
                f"{plan['plan_description']}",
                parse_mode='Markdown'
            )

            # Проверяем, есть ли предстоящие тренировки
            has_pending_trainings = False
            total_training_days = len(plan['plan_data']['training_days'])

            # Считаем количество предстоящих тренировок
            pending_count = total_training_days - len(processed_days)

            # Если есть предстоящие тренировки, отправляем сначала их
            if pending_count > 0:
                await update.message.reply_text(
                    "📆 *Предстоящие тренировки:*",
                    parse_mode='Markdown'
                )

                # Отправляем только предстоящие дни тренировок
                pending_shown = False
                for idx, day in enumerate(plan['plan_data']['training_days']):
                    training_day_num = idx + 1

                    # Пропускаем обработанные тренировки
                    if training_day_num in processed_days:
                        continue

                    pending_shown = True

                    # Определяем поле с типом тренировки (может быть 'type' или 'training_type')
                    training_type = day.get('training_type') or day.get('type', 'Не указан')

                    training_message = (
                        f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {training_type}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )

                    # Добавляем кнопки для предстоящих тренировок
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", 
                                          callback_data=f"complete_{plan['id']}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", 
                                          callback_data=f"cancel_{plan['id']}_{training_day_num}")]
                    ])

                    await update.message.reply_text(
                        training_message,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )

                # На случай, если что-то пошло не так и у нас нет предстоящих тренировок
                if not pending_shown:
                    await update.message.reply_text(
                        "⚠️ Не удалось найти предстоящие тренировки, хотя они должны быть. "
                        "Это может быть ошибкой в данных."
                    )

            # Если есть завершенные или отмененные тренировки, показываем их после предстоящих
            if completed or canceled:
                # Создаем кнопку для отображения истории тренировок
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📜 Показать историю тренировок", 
                                      callback_data=f"show_history_{plan['id']}")]
                ])

                # Информация о прогрессе
                total_completed_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan['id'])

                await update.message.reply_text(
                    f"📊 *Статистика плана:*\n\n"
                    f"Всего тренировок: {total_training_days}\n"
                    f"Выполнено: {len(completed)}\n"
                    f"Отменено: {len(canceled)}\n"
                    f"Осталось: {pending_count}\n"
                    f"Пройдено километров: {total_completed_distance:.1f} км",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )

            # Если все тренировки выполнены или отменены, предлагаем продолжить тренировки
            if pending_count == 0:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Продолжить тренировки", 
                                      callback_data=f"continue_plan_{plan['id']}")]
                ])

                await update.message.reply_text(
                    "🎉 Все тренировки в текущем плане выполнены или отменены! "
                    "Хотите продолжить тренировки с учетом вашего прогресса?",
                    reply_markup=keyboard
                )

        elif text == "🆕 Создать новый план":
            # Проверяем статус оплаты пользователя
            payment_status = DBManager.get_payment_status(db_user_id)
            if not payment_status or not payment_status.get('payment_agreed', False):
                # Если статуса оплаты нет в БД, но есть в пользовательских данных
                if context.user_data.get('payment_agreed', False):
                    # Сохраняем статус оплаты в БД
                    DBManager.save_payment_status(db_user_id, True)
                else:
                    # Предлагаем оплату
                    reply_markup = ReplyKeyboardMarkup(
                        [
                            ['Да, буду платить 500 рублей в месяц'],
                            ['Нет. Я и так МАШИНА Ой БОЙ!']
                        ],
                        one_time_keyboard=True,
                        resize_keyboard=True
                    )

                    await update.message.reply_text(
                        "Для доступа к функции создания плана тренировок необходимо оформить подписку. " +
                        "Бот стоит 500 рублей в месяц с гарантией добавления новых фичей и легкой отменой!",
                        reply_markup=reply_markup
                    )

                    # Сохраняем состояние - ожидаем ответа на вопрос об оплате
                    context.user_data['awaiting_payment_confirmation'] = True
                    return

            # Получаем профиль пользователя
            profile = DBManager.get_runner_profile(db_user_id)

            if not profile:
                await update.message.reply_text(
                    "⚠️ У вас еще нет профиля бегуна. Используйте команду /start, чтобы создать его."
                )
                return

            # Проверяем, есть ли уже план тренировок
            existing_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

            # Если у пользователя уже есть план, спрашиваем подтверждение
            if existing_plan:
                # Создаем inline кнопки для подтверждения
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Да, создать новый план", callback_data="confirm_new_plan")],
                    [InlineKeyboardButton("✏️ Сначала обновить профиль", callback_data="update_profile_first")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_new_plan")]
                ])

                await update.message.reply_text(
                    "⚠️ У вас уже есть план тренировок.\n\n"
                    "Хотите создать новый план с теми же параметрами профиля? "
                    "Это заменит ваш текущий план тренировок.\n\n"
                    "Возможно, вы хотите сначала обновить свой профиль, чтобы новый план учитывал изменения в ваших целях или физической форме?",
                    reply_markup=keyboard
                )
                return

            # Если у пользователя нет плана, то начинаем генерацию нового плана
            # Отправляем сообщение с котиком
            with open("attached_assets/котик.jpeg", "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption="⏳ Генерирую персонализированный план тренировок. Это может занять некоторое время...\n\nМой котик всегда готов к любой задаче! 🐱💪"
                )

            # Генерируем новый план
            try:
                # Инициализируем сервис OpenAI
                openai_service = OpenAIService()

                # Генерируем план
                plan = openai_service.generate_training_plan(profile)

                # Сохраняем план в БД
                plan_id = TrainingPlanManager.save_training_plan(db_user_id, plan)

                if not plan_id:
                    await update.message.reply_text(
                        "❌ Произошла ошибка при сохранении плана тренировок."
                    )
                    return

                # Получаем сохраненный план
                saved_plan = TrainingPlanManager.get_latest_training_plan(db_user_id)

                # Отправляем план пользователю
                await update.message.reply_text(
                    f"✅ Ваш персонализированный план тренировок готов!\n\n"
                    f"*{saved_plan['plan_name']}*\n\n"
                    f"{saved_plan['plan_description']}",
                    parse_mode='Markdown'
                )

                # Отправляем приглашение в чат БЕТА тестеров
                await update.message.reply_text("Если есть желание и время заходите в чатик БЕТА тестеров https://t.me/+oiEFpRKHRPA3ZDA6")

                # Показываем главное меню после генерации плана
                await send_main_menu(update, context, "Ваш план создан. Что еще вы хотите сделать?")

                # Отправляем дни тренировок
                # Определяем структуру плана
                training_days = []
                if 'training_days' in saved_plan:
                    training_days = saved_plan['training_days']
                elif 'plan_data' in saved_plan and isinstance(saved_plan['plan_data'], dict) and 'training_days' in saved_plan['plan_data']:
                    training_days = saved_plan['plan_data']['training_days']
                else:
                    logging.error(f"Неверная структура плана: {saved_plan.keys()}")
                    await update.message.reply_text("❌ Ошибка в структуре плана тренировок.")
                    return

                for idx, day in enumerate(training_days):
                    training_day_num = idx + 1

                    # Создаем сообщение с днем тренировки
                    # Определяем поле с типом тренировки (может быть 'type' или 'training_type')
                    training_type = day.get('training_type') or day.get('type', 'Не указан')

                    training_message = (
                        f"*День {training_day_num}: {day['day']} ({day['date']})*\n"
                        f"Тип: {training_type}\n"
                        f"Дистанция: {day['distance']}\n"
                        f"Темп: {day['pace']}\n\n"
                        f"{day['description']}"
                    )

                    # Добавляем кнопки
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Отметить как выполненное", 
                                             callback_data=f"complete_{saved_plan['id']}_{training_day_num}")],
                        [InlineKeyboardButton("❌ Отменить", 
                                             callback_data=f"cancel_{saved_plan['id']}_{training_day_num}")]
                    ])

                    await update.message.reply_text(
                        training_message,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )

            except Exception as e:
                logging.error(f"Ошибка генерации плана: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка при генерации плана тренировок. Пожалуйста, попробуйте позже."
                )

                # Показываем главное меню после ошибки генерации плана
                await send_main_menu(update, context, "Что вы хотите сделать?")

        # Обработка "✏️ Обновить мой профиль" теперь происходит через ConversationHandler

        elif text == "🏃‍♂️ Показать мой профиль":
            # Показываем текущий профиль пользователя
            runner_profile = DBManager.get_runner_profile(db_user_id)

            if not runner_profile:
                await update.message.reply_text(
                    "⚠️ У вас еще нет профиля бегуна. Создайте его с помощью команды /plan."
                )
                # Показываем главное меню даже если профиля нет
                await send_main_menu(update, context)
                return

            # Форматируем информацию о профиле для отображения
            weekly_volume = format_weekly_volume(runner_profile.get('weekly_volume', 0))

            profile_text = (
                f"🏃‍♂️ *Ваш профиль бегуна:*\n\n"
                f"📏 Дистанция: {runner_profile.get('distance', 'Не указано')} км\n"
                f"📅 Дата соревнований: {runner_profile.get('competition_date', 'Не указано')}\n"
                f"⚧ Пол: {runner_profile.get('gender', 'Не указано')}\n"
                f"🎂 Возраст: {runner_profile.get('age', 'Не указано')} лет\n"
                f"📏 Рост: {runner_profile.get('height', 'Не указано')} см\n"
                f"⚖️ Вес: {runner_profile.get('weight', 'Не указано')} кг\n"
                f"🏅 Опыт бега: {runner_profile.get('experience', 'Не указано')}\n"
                f"🎯 Цель: {runner_profile.get('goal', 'Не указано')}\n"
                f"⏱️ Целевое время: {runner_profile.get('target_time', 'Не указано')}\n"
                f"🗣️ Комфортный темп: {runner_profile.get('comfortable_pace', 'Не указано')}\n"
                f"📊 Еженедельный объем бега: {weekly_volume}\n"
                f"🗓️ Дата начала тренировок: {runner_profile.get('training_start_date', 'Не указано')}\n"
                f"🗓️ Количество тренировок в неделю: {runner_profile.get('training_days_per_week', 'Не указано')}\n"
                f"📆 Предпочитаемые дни тренировок: {runner_profile.get('preferred_training_days', 'Не указано')}\n\n"
                f"Ваш профиль был создан: {runner_profile.get('created_at', 'Не указано')}\n"
                f"Последнее обновление: {runner_profile.get('updated_at', 'Не указано')}"
            )

            # Предлагаем кнопку для обновления профиля
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Обновить мой профиль", callback_data="update_profile")]
            ])

            await update.message.reply_text(
                profile_text, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )

            # Показываем главное меню после показа профиля
            await send_main_menu(update, context, "Что еще вы хотите сделать с вашим профилем?")

    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler), group=2)

    # Add callback query handler for inline buttons с группой более низкого приоритета
    application.add_handler(CallbackQueryHandler(callback_query_handler), group=2)

    return application
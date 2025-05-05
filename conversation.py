import re
from datetime import datetime

# Импорты из python-telegram-bot
try:
    from telegram import ReplyKeyboardMarkup, KeyboardButton, Update, ReplyKeyboardRemove
    from telegram.ext import CallbackContext, ConversationHandler
except ImportError:
    # Для LSP - чтобы избежать ошибок проверки типов
    class Update:
        pass
    
    class CallbackContext:
        pass
    
    class ConversationHandler:
        END = -1

from config import STATES, logging
from db_manager import DBManager

class RunnerProfileConversation:
    """Manages the conversation flow for collecting runner profile information."""
    
    def __init__(self):
        """Initialize the conversation handler with empty profile data dict."""
        self.user_data = {}
    
    async def start_update(self, update: Update, context: CallbackContext):
        """Start the conversation for updating profile information."""
        user = update.effective_user
        telegram_id = user.id
        
        # Получаем id пользователя в БД
        db_user_id = DBManager.get_user_id(telegram_id)
        if not db_user_id:
            await update.message.reply_text(
                "⚠️ Сначала нужно создать профиль бегуна. Используйте команду /start."
            )
            return ConversationHandler.END
        
        # Получаем текущий профиль бегуна
        runner_profile = DBManager.get_runner_profile(db_user_id)
        if not runner_profile:
            await update.message.reply_text(
                "⚠️ У вас еще нет профиля бегуна. Создайте его с помощью команды /start."
            )
            return ConversationHandler.END
        
        # Начинаем диалог обновления профиля с первого шага - дистанции
        # Показываем текущее значение для каждого поля
        context.user_data['db_user_id'] = db_user_id
        context.user_data['profile_data'] = {}
        
        # Добавляем информацию, что это обновление существующего профиля
        context.user_data['is_profile_update'] = True
        
        # Запрос новой дистанции
        await update.message.reply_text(
            f"Начинаем обновление вашего профиля бегуна.\n"
            f"Вы можете отменить процесс в любой момент, отправив /cancel.\n\n"
            f"Текущая дистанция: {runner_profile.get('distance', 'Не указано')} км\n"
            f"Введите новую целевую дистанцию (в км):",
            reply_markup=ReplyKeyboardMarkup(
                [['5', '10'], ['21', '42']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        
        return STATES['DISTANCE']
    
    async def start(self, update: Update, context: CallbackContext):
        """Start the conversation and save user information."""
        user = update.effective_user
        telegram_id = user.id
        
        # Save user to database
        user_id = DBManager.add_user(
            telegram_id,
            user.username,
            user.first_name,
            user.last_name
        )
        
        if not user_id:
            await update.message.reply_text(
                "Извините, произошла ошибка при запуске диалога. Пожалуйста, попробуйте позже."
            )
            return ConversationHandler.END
            
        # Проверяем, есть ли у пользователя уже профиль
        existing_profile = DBManager.get_runner_profile(user_id)
        if existing_profile:
            # У пользователя уже есть профиль
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}! У вас уже есть профиль бегуна."
            )
            
            # Импортируем функцию для отображения главного меню
            from bot_modified import send_main_menu
            
            # Отправляем главное меню
            await send_main_menu(update, context, "Что вы хотите сделать?")
            
            return ConversationHandler.END
        
        # Store user_id in context.user_data
        context.user_data['db_user_id'] = user_id
        context.user_data['profile_data'] = {}
        
        # Предложить стандартные дистанции
        reply_markup = ReplyKeyboardMarkup(
            [['5', '10'], ['21', '42']], 
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я помогу вам создать ваш профиль бегуна. "
            "Давайте начнем с основной информации о ваших беговых целях.\n\n"
            "Какую дистанцию бега вы планируете пробежать (в километрах)?",
            reply_markup=reply_markup
        )
        
        return STATES['DISTANCE']
    
    async def collect_distance(self, update: Update, context: CallbackContext):
        """Collect and validate running distance."""
        text = update.message.text.strip()
        
        # Validate distance
        try:
            distance = float(text.replace(',', '.'))
            if distance <= 0:
                await update.message.reply_text(
                    "Пожалуйста, введите положительное значение дистанции."
                )
                return STATES['DISTANCE']
            
            context.user_data['profile_data']['distance'] = distance
            
            # Добавляем кнопку "Нет" для выбора
            reply_markup = ReplyKeyboardMarkup(
                [['Нет']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                f"Отлично! Вы планируете пробежать {distance} км.\n\n"
                "Когда у вас соревнование? Пожалуйста, введите дату в формате ДД.ММ.ГГГГ "
                "или выберите 'Нет', если у вас нет конкретной даты соревнования.",
                reply_markup=reply_markup
            )
            return STATES['COMPETITION_DATE']
            
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите корректное числовое значение дистанции в километрах."
            )
            return STATES['DISTANCE']
    
    async def collect_competition_date(self, update: Update, context: CallbackContext):
        """Collect and validate competition date."""
        text = update.message.text.strip()
        
        # Обработка варианта "Нет"
        if text == 'Нет':
            context.user_data['profile_data']['competition_date'] = 'Нет конкретной даты'
            
            # Ask for gender with keyboard
            reply_markup = ReplyKeyboardMarkup(
                [['Мужской', 'Женский']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "Укажите ваш пол:",
                reply_markup=reply_markup
            )
            return STATES['GENDER']
        
        # Validate date format
        date_pattern = r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$'
        match = re.match(date_pattern, text)
        
        if not match:
            reply_markup = ReplyKeyboardMarkup(
                [['Нет']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 25.12.2023) "
                "или выберите 'Нет', если у вас нет конкретной даты соревнования.",
                reply_markup=reply_markup
            )
            return STATES['COMPETITION_DATE']
        
        day, month, year = map(int, match.groups())
        
        try:
            date_obj = datetime(year, month, day)
            today = datetime.now()
            
            if date_obj < today:
                reply_markup = ReplyKeyboardMarkup(
                    [['Нет']],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                await update.message.reply_text(
                    "Дата соревнования должна быть в будущем. Пожалуйста, введите корректную дату "
                    "или выберите 'Нет', если у вас нет конкретной даты соревнования.",
                    reply_markup=reply_markup
                )
                return STATES['COMPETITION_DATE']
            
            context.user_data['profile_data']['competition_date'] = text
            
            # Ask for gender with keyboard
            reply_markup = ReplyKeyboardMarkup(
                [['Мужской', 'Женский']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "Укажите ваш пол:",
                reply_markup=reply_markup
            )
            return STATES['GENDER']
            
        except ValueError:
            reply_markup = ReplyKeyboardMarkup(
                [['Нет']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, введите корректную дату в формате ДД.ММ.ГГГГ "
                "или выберите 'Нет', если у вас нет конкретной даты соревнования.",
                reply_markup=reply_markup
            )
            return STATES['COMPETITION_DATE']
    
    async def collect_gender(self, update: Update, context: CallbackContext):
        """Collect gender information."""
        text = update.message.text.strip()
        
        if text not in ['Мужской', 'Женский']:
            reply_markup = ReplyKeyboardMarkup(
                [['Мужской', 'Женский']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, выберите 'Мужской' или 'Женский'.",
                reply_markup=reply_markup
            )
            return STATES['GENDER']
        
        context.user_data['profile_data']['gender'] = text
        
        await update.message.reply_text(
            "Сколько вам лет?",
            reply_markup=ReplyKeyboardRemove()
        )
        return STATES['AGE']
    
    async def collect_age(self, update: Update, context: CallbackContext):
        """Collect and validate age."""
        text = update.message.text.strip()
        
        try:
            age = int(text)
            if age < 10 or age > 120:
                await update.message.reply_text(
                    "Пожалуйста, введите корректный возраст от 10 до 120 лет."
                )
                return STATES['AGE']
            
            context.user_data['profile_data']['age'] = age
            
            await update.message.reply_text(
                "Какой у вас рост в сантиметрах?"
            )
            return STATES['HEIGHT']
            
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите ваш возраст целым числом."
            )
            return STATES['AGE']
    
    async def collect_height(self, update: Update, context: CallbackContext):
        """Collect and validate height."""
        text = update.message.text.strip()
        
        try:
            height = float(text.replace(',', '.'))
            if height < 100 or height > 250:
                await update.message.reply_text(
                    "Пожалуйста, введите корректный рост от 100 до 250 см."
                )
                return STATES['HEIGHT']
            
            context.user_data['profile_data']['height'] = height
            
            await update.message.reply_text(
                "Какой у вас вес в килограммах?"
            )
            return STATES['WEIGHT']
            
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите корректное числовое значение роста в сантиметрах."
            )
            return STATES['HEIGHT']
    
    async def collect_weight(self, update: Update, context: CallbackContext):
        """Collect and validate weight."""
        text = update.message.text.strip()
        
        try:
            weight = float(text.replace(',', '.'))
            if weight < 30 or weight > 250:
                await update.message.reply_text(
                    "Пожалуйста, введите корректный вес от 30 до 250 кг."
                )
                return STATES['WEIGHT']
            
            context.user_data['profile_data']['weight'] = weight
            
            # Пропускаем вопрос об опыте бега
            # Устанавливаем значение по умолчанию для совместимости с БД
            context.user_data['profile_data']['experience'] = 'N/A'
            
            # Ask about running goal
            reply_markup = ReplyKeyboardMarkup(
                [['Просто финишировать', 'Улучшить время']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "Какова ваша цель на этом забеге?",
                reply_markup=reply_markup
            )
            return STATES['GOAL']
            
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите корректное числовое значение веса в килограммах."
            )
            return STATES['WEIGHT']
    
    async def collect_experience(self, update: Update, context: CallbackContext):
        """Collect running experience."""
        text = update.message.text.strip()
        valid_experiences = [
            'Полный новичок',
            'Менее 1 года',
            '1-3 года',
            '3-5 лет',
            'Более 5 лет'
        ]
        
        if text not in valid_experiences:
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Полный новичок'],
                    ['Менее 1 года'],
                    ['1-3 года'],
                    ['3-5 лет'],
                    ['Более 5 лет']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, выберите один из предложенных вариантов.",
                reply_markup=reply_markup
            )
            return STATES['EXPERIENCE']
        
        context.user_data['profile_data']['experience'] = text
        
        # Ask about running goal
        reply_markup = ReplyKeyboardMarkup(
            [['Просто финишировать', 'Улучшить время']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "Какова ваша цель на этом забеге?",
            reply_markup=reply_markup
        )
        return STATES['GOAL']
    
    async def collect_goal(self, update: Update, context: CallbackContext):
        """Collect runner's goal."""
        text = update.message.text.strip()
        
        if text not in ['Просто финишировать', 'Улучшить время']:
            reply_markup = ReplyKeyboardMarkup(
                [['Просто финишировать', 'Улучшить время']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, выберите 'Просто финишировать' или 'Улучшить время'.",
                reply_markup=reply_markup
            )
            return STATES['GOAL']
        
        context.user_data['profile_data']['goal'] = text
        
        if text == 'Улучшить время':
            await update.message.reply_text(
                "Какое у вас целевое время финиша? Пожалуйста, введите в формате ЧЧ:ММ:СС",
                reply_markup=ReplyKeyboardRemove()
            )
            return STATES['TARGET_TIME']
        else:
            # Skip target time question for 'Just finish' goal
            context.user_data['profile_data']['target_time'] = 'N/A'
            
            # Ask about fitness level
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Начинающий'],
                    ['Средний'],
                    ['Продвинутый'],
                    ['Элитный']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "Как бы вы оценили уровень своей физической подготовки?",
                reply_markup=reply_markup
            )
            return STATES['FITNESS']
    
    async def collect_target_time(self, update: Update, context: CallbackContext):
        """Collect and validate target finish time."""
        text = update.message.text.strip()
        
        # Validate time format
        time_pattern = r'^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$'
        match = re.match(time_pattern, text)
        
        if not match:
            await update.message.reply_text(
                "Пожалуйста, введите время в формате ЧЧ:ММ или ЧЧ:ММ:СС (например, 01:30:00)"
            )
            return STATES['TARGET_TIME']
        
        context.user_data['profile_data']['target_time'] = text
        
        # Ask about fitness level
        reply_markup = ReplyKeyboardMarkup(
            [
                ['Начинающий'],
                ['Средний'],
                ['Продвинутый'],
                ['Элитный']
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "Как бы вы оценили уровень своей физической подготовки?",
            reply_markup=reply_markup
        )
        return STATES['FITNESS']
    
    async def collect_fitness(self, update: Update, context: CallbackContext):
        """Collect fitness level."""
        text = update.message.text.strip()
        valid_levels = ['Начинающий', 'Средний', 'Продвинутый', 'Элитный']
        
        if text not in valid_levels:
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Начинающий'],
                    ['Средний'],
                    ['Продвинутый'],
                    ['Элитный']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, выберите один из предложенных уровней физической подготовки.",
                reply_markup=reply_markup
            )
            return STATES['FITNESS']
        
        context.user_data['profile_data']['fitness_level'] = text
        
        # Добавляем стандартные варианты объемов бега
        reply_markup = ReplyKeyboardMarkup(
            [
                ['0-10'],
                ['10-25'],
                ['25-50'],
                ['50+']
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "Какой у вас текущий еженедельный объем бега в километрах?",
            reply_markup=reply_markup
        )
        return STATES['WEEKLY_VOLUME']
    
    async def collect_weekly_volume(self, update: Update, context: CallbackContext):
        """Collect and validate weekly running volume."""
        text = update.message.text.strip()
        
        # Обработка диапазонов
        if text == '0-10':
            volume_text = '0-10'
            volume = 5  # среднее значение диапазона
        elif text == '10-25':
            volume_text = '10-25'
            volume = 17.5  # среднее значение диапазона
        elif text == '25-50':
            volume_text = '25-50'
            volume = 37.5  # среднее значение диапазона
        elif text == '50+':
            volume_text = '50+'
            volume = 50  # минимальное значение диапазона
        else:
            # Попытка преобразовать в число, если введено не из диапазонов
            try:
                volume = float(text.replace(',', '.'))
                volume_text = f"{volume}"
                
                if volume < 0 or volume > 500:
                    # Добавляем кнопки с вариантами объема при ошибке
                    reply_markup = ReplyKeyboardMarkup(
                        [
                            ['0-10'],
                            ['10-25'],
                            ['25-50'],
                            ['50+']
                        ],
                        one_time_keyboard=True,
                        resize_keyboard=True
                    )
                    await update.message.reply_text(
                        "Пожалуйста, введите корректный еженедельный объем бега от 0 до 500 км.",
                        reply_markup=reply_markup
                    )
                    return STATES['WEEKLY_VOLUME']
            except ValueError:
                # Добавляем кнопки с вариантами объема при ошибке
                reply_markup = ReplyKeyboardMarkup(
                    [
                        ['0-10'],
                        ['10-25'],
                        ['25-50'],
                        ['50+']
                    ],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                await update.message.reply_text(
                    "Пожалуйста, выберите один из предложенных вариантов или введите корректное числовое значение.",
                    reply_markup=reply_markup
                )
                return STATES['WEEKLY_VOLUME']
        
        # Сохраняем и числовое и текстовое представление
        context.user_data['profile_data']['weekly_volume'] = volume
        context.user_data['profile_data']['weekly_volume_text'] = volume_text
        
        # Переходим к вопросу о дате начала тренировок
        reply_markup = ReplyKeyboardMarkup(
            [['Не знаю']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "Когда вы планируете начать тренировки? Пожалуйста, укажите дату в формате ДД.ММ "
            "или выберите 'Не знаю', если хотите начать тренировки сразу.",
            reply_markup=reply_markup
        )
        return STATES['TRAINING_START_DATE']
    
    async def collect_training_start_date(self, update: Update, context: CallbackContext):
        """Collect and validate training start date."""
        text = update.message.text
        
        if text == 'Не знаю':
            # Используем текущую дату
            today = datetime.now().strftime("%d.%m.%Y")
            context.user_data['profile_data']['training_start_date'] = today
            context.user_data['profile_data']['training_start_date_text'] = "Сегодня"
        else:
            # Валидация формата даты
            date_pattern = r'^(\d{1,2})\.(\d{1,2})$'
            match = re.match(date_pattern, text)
            
            if not match:
                await update.message.reply_text(
                    "Пожалуйста, введите дату в формате ДД.ММ (например, 15.06) или выберите 'Не знаю'.",
                    reply_markup=ReplyKeyboardMarkup(
                        [['Не знаю']],
                        one_time_keyboard=True,
                        resize_keyboard=True
                    )
                )
                return STATES['TRAINING_START_DATE']
            
            day, month = map(int, match.groups())
            current_year = datetime.now().year
            
            # Проверка валидности даты
            try:
                # Добавляем текущий год к дате
                date_obj = datetime(current_year, month, day)
                date_str = date_obj.strftime("%d.%m.%Y")
                
                context.user_data['profile_data']['training_start_date'] = date_str
                context.user_data['profile_data']['training_start_date_text'] = text
            except ValueError:
                await update.message.reply_text(
                    "Пожалуйста, введите корректную дату. "
                    "День должен быть от 1 до 31, месяц - от 1 до 12.",
                    reply_markup=ReplyKeyboardMarkup(
                        [['Не знаю']],
                        one_time_keyboard=True,
                        resize_keyboard=True
                    )
                )
                return STATES['TRAINING_START_DATE']
        
        # Спрашиваем сколько дней в неделю пользователь хочет тренироваться
        reply_markup = ReplyKeyboardMarkup(
            [['2', '3', '4'], ['5', '6', '7']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "Сколько дней в неделю вы хотите тренироваться?",
            reply_markup=reply_markup
        )
        return STATES['TRAINING_DAYS_PER_WEEK']
    
    async def collect_training_days_per_week(self, update: Update, context: CallbackContext):
        """Collect and validate training days per week."""
        text = update.message.text.strip()
        
        try:
            days = int(text)
            if days < 1 or days > 7:
                await update.message.reply_text(
                    "Пожалуйста, введите число от 1 до 7:"
                )
                return STATES['TRAINING_DAYS_PER_WEEK']
                
            # Сохраняем количество дней тренировок
            context.user_data['profile_data']['training_days_per_week'] = text
            context.user_data['days_to_select'] = days
            
            # Предлагаем выбрать дни недели для тренировок
            days_of_week = [["Пн", "Вт", "Ср"], ["Чт", "Пт", "Сб", "Вс"]]
            reply_markup = ReplyKeyboardMarkup(
                days_of_week,
                one_time_keyboard=False,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                f"Выберите {days} дней недели, когда вам удобно тренироваться.\n"
                f"Отправьте выбранные дни через запятую (например: Пн,Ср,Пт):",
                reply_markup=reply_markup
            )
            return STATES['PREFERRED_TRAINING_DAYS']
            
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите число от 1 до 7:"
            )
            return STATES['TRAINING_DAYS_PER_WEEK']
    
    async def collect_preferred_training_days(self, update: Update, context: CallbackContext):
        """Collect and validate preferred training days."""
        text = update.message.text.strip()
        
        # Если пользователь подтверждает выбор дней, который не соответствует требуемому количеству
        if context.user_data.get('confirming_days_mismatch'):
            if text == 'Да, продолжить с текущим выбором':
                # Используем временно сохраненные дни
                selected_days = context.user_data.get('temp_selected_days', "")
                context.user_data['profile_data']['preferred_training_days'] = selected_days
                
                # Очищаем временные данные
                del context.user_data['confirming_days_mismatch']
                del context.user_data['temp_selected_days']
                if 'days_to_select' in context.user_data:
                    del context.user_data['days_to_select']
                if 'selected_days_list' in context.user_data:
                    del context.user_data['selected_days_list']
                
                # Переходим к экрану подтверждения данных
                return await self.show_confirmation(update, context)
            elif text == 'Нет, выбрать заново':
                # Возвращаемся к выбору дней
                days_to_select = int(context.user_data.get('days_to_select', 3))
                
                days_of_week = [["Пн", "Вт", "Ср"], ["Чт", "Пт", "Сб", "Вс"]]
                reply_markup = ReplyKeyboardMarkup(
                    days_of_week,
                    one_time_keyboard=False,
                    resize_keyboard=True
                )
                
                # Очищаем временные данные
                del context.user_data['confirming_days_mismatch']
                if 'temp_selected_days' in context.user_data:
                    del context.user_data['temp_selected_days']
                if 'selected_days_list' in context.user_data:
                    del context.user_data['selected_days_list']
                
                await update.message.reply_text(
                    f"Выберите {days_to_select} дней недели, когда вам удобно тренироваться.\n"
                    f"Отправьте выбранные дни через запятую (например: Пн,Ср,Пт):",
                    reply_markup=reply_markup
                )
                return STATES['PREFERRED_TRAINING_DAYS']
            else:
                # Неожиданный ответ, запрашиваем снова
                reply_markup = ReplyKeyboardMarkup(
                    [['Да, продолжить с текущим выбором', 'Нет, выбрать заново']],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                
                await update.message.reply_text(
                    "Пожалуйста, выберите один из вариантов ниже:",
                    reply_markup=reply_markup
                )
                return STATES['PREFERRED_TRAINING_DAYS']
        
        # Проверяем, если это один день недели (нажата кнопка)
        valid_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        if text in valid_days:
            # Пользователь нажал кнопку с одним днем недели
            # Добавляем день в список выбранных дней
            selected_days_list = context.user_data.get('selected_days_list', [])
            
            # Проверяем, не выбран ли уже этот день
            if text in selected_days_list:
                # День уже выбран, удаляем его из списка
                selected_days_list.remove(text)
            else:
                # Добавляем день в список
                selected_days_list.append(text)
            
            # Сохраняем обновленный список
            context.user_data['selected_days_list'] = selected_days_list
            days_to_select = int(context.user_data.get('days_to_select', 3))
            
            # Сообщаем пользователю о текущем выборе
            current_selection = ", ".join(selected_days_list) if selected_days_list else "не выбрано"
            
            # Создаем клавиатуру для продолжения выбора или завершения
            days_of_week = [["Пн", "Вт", "Ср"], ["Чт", "Пт", "Сб", "Вс"]]
            
            # Добавляем кнопку завершения выбора, если уже есть выбранные дни
            if selected_days_list:
                days_of_week.append(["✅ Завершить выбор"])
            
            reply_markup = ReplyKeyboardMarkup(
                days_of_week,
                one_time_keyboard=False,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                f"Вы выбрали {len(selected_days_list)} из {days_to_select} дней: {current_selection}\n\n"
                f"Продолжите выбор дней или нажмите 'Завершить выбор', когда закончите.",
                reply_markup=reply_markup
            )
            return STATES['PREFERRED_TRAINING_DAYS']
            
        # Проверяем, если пользователь нажал кнопку завершения выбора
        if text == "✅ Завершить выбор":
            selected_days_list = context.user_data.get('selected_days_list', [])
            
            if not selected_days_list:
                await update.message.reply_text(
                    "Вы не выбрали ни одного дня недели. Пожалуйста, выберите как минимум один день:"
                )
                return STATES['PREFERRED_TRAINING_DAYS']
                
            # Преобразуем список в строку
            selected_days_str = ",".join(selected_days_list)
            
            # Проверяем, соответствует ли количество выбранных дней количеству дней тренировок
            days_to_select = int(context.user_data.get('days_to_select', 3))
            if len(selected_days_list) != days_to_select:
                # Спрашиваем подтверждение, если количество не совпадает
                context.user_data['temp_selected_days'] = selected_days_str
                
                reply_markup = ReplyKeyboardMarkup(
                    [['Да, продолжить с текущим выбором', 'Нет, выбрать заново']],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                
                await update.message.reply_text(
                    f"Вы выбрали {len(selected_days_list)} дней, хотя указали, что хотите тренироваться {days_to_select} дней в неделю.\n\n"
                    f"Хотите продолжить с текущим выбором ({', '.join(selected_days_list)})?\n\n"
                    f"Если нет, вы сможете выбрать дни заново.",
                    reply_markup=reply_markup
                )
                
                # Сохраняем состояние для проверки ответа в следующем шаге
                context.user_data['confirming_days_mismatch'] = True
                return STATES['PREFERRED_TRAINING_DAYS']
            
            # Если количество соответствует
            context.user_data['profile_data']['preferred_training_days'] = selected_days_str
            
            # Удаляем временные данные
            if 'temp_selected_days' in context.user_data:
                del context.user_data['temp_selected_days']
            if 'confirming_days_mismatch' in context.user_data:
                del context.user_data['confirming_days_mismatch']
            if 'days_to_select' in context.user_data:
                del context.user_data['days_to_select']
            if 'selected_days_list' in context.user_data:
                del context.user_data['selected_days_list']
                
            # Переходим к экрану подтверждения данных
            return await self.show_confirmation(update, context)
        
        # Обработка обычного ввода через запятую
        selected_days = [day.strip() for day in text.split(',')]
        
        # Проверяем, что все введенные дни являются валидными днями недели
        if not all(day in valid_days for day in selected_days):
            await update.message.reply_text(
                "Пожалуйста, выберите только допустимые дни недели (Пн, Вт, Ср, Чт, Пт, Сб, Вс) и разделите их запятыми:"
            )
            return STATES['PREFERRED_TRAINING_DAYS']
        
        # Проверяем, что нет дубликатов
        if len(selected_days) != len(set(selected_days)):
            await update.message.reply_text(
                "Вы указали некоторые дни более одного раза. Пожалуйста, укажите каждый день только один раз:"
            )
            return STATES['PREFERRED_TRAINING_DAYS']
        
        # Проверяем, соответствует ли количество выбранных дней количеству дней тренировок
        days_to_select = int(context.user_data.get('days_to_select', 3))
        if len(selected_days) != days_to_select:
            # Спрашиваем подтверждение, если количество не совпадает
            context.user_data['temp_selected_days'] = text
            
            reply_markup = ReplyKeyboardMarkup(
                [['Да, продолжить с текущим выбором', 'Нет, выбрать заново']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                f"Вы выбрали {len(selected_days)} дней, хотя указали, что хотите тренироваться {days_to_select} дней в неделю.\n\n"
                f"Хотите продолжить с текущим выбором ({', '.join(selected_days)})?\n\n"
                f"Если нет, вы сможете выбрать дни заново.",
                reply_markup=reply_markup
            )
            
            # Сохраняем состояние для проверки ответа в следующем шаге
            context.user_data['confirming_days_mismatch'] = True
            return STATES['PREFERRED_TRAINING_DAYS']
        
        # Если количество соответствует или пользователь подтвердил выбор
        context.user_data['profile_data']['preferred_training_days'] = text
        
        # Удаляем временные данные
        if 'temp_selected_days' in context.user_data:
            del context.user_data['temp_selected_days']
        if 'confirming_days_mismatch' in context.user_data:
            del context.user_data['confirming_days_mismatch']
        if 'days_to_select' in context.user_data:
            del context.user_data['days_to_select']
        if 'selected_days_list' in context.user_data:
            del context.user_data['selected_days_list']
        
        # Переходим к экрану подтверждения данных
        return await self.show_confirmation(update, context)
    
    async def show_confirmation(self, update: Update, context: CallbackContext):
        """Display profile summary and ask for confirmation."""
        # Display summary of collected information
        profile = context.user_data['profile_data']
        summary = (
            "Отлично! Вот сводка вашего профиля бегуна:\n\n"
            f"🏃 Целевая дистанция: {profile['distance']} км\n"
            f"📅 Дата соревнования: {profile['competition_date']}\n"
            f"👤 Пол: {profile['gender']}\n"
            f"🎂 Возраст: {profile['age']}\n"
            f"📏 Рост: {profile['height']} см\n"
            f"⚖️ Вес: {profile['weight']} кг\n"
            f"🎯 Цель: {profile['goal']}\n"
            f"📆 Дата начала тренировок: {profile.get('training_start_date_text', 'Не указана')}\n"
        )
        
        if profile['goal'] == 'Улучшить время':
            summary += f"⏱️ Целевое время: {profile['target_time']}\n"
            
        summary += (
            f"💪 Уровень физической подготовки: {profile['fitness_level']}\n"
            f"📊 Еженедельный объем: {profile['weekly_volume_text']} км\n"
            f"🗓️ Количество тренировок в неделю: {profile['training_days_per_week']}\n"
            f"📆 Предпочитаемые дни тренировок: {profile['preferred_training_days']}\n\n"
            "Эта информация верна?"
        )
        
        reply_markup = ReplyKeyboardMarkup(
            [['Да, сохранить мой профиль', 'Нет, начать заново']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            summary,
            reply_markup=reply_markup
        )
        return STATES['CONFIRMATION']
    
    async def confirm_data(self, update: Update, context: CallbackContext):
        """Handle user confirmation of collected data."""
        text = update.message.text.strip()
        
        if text == 'Да, сохранить мой профиль':
            user_id = context.user_data.get('db_user_id')
            profile_data = context.user_data.get('profile_data', {})
            
            # Save profile to database
            if DBManager.save_runner_profile(user_id, profile_data):
                # Устанавливаем флаг обновления профиля для предложения создания нового плана
                context.user_data['profile_updated'] = True
                
                await update.message.reply_text(
                    "🎉 Отлично! Ваш профиль бегуна успешно сохранен. "
                    "Спасибо за предоставленную информацию!",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                # Импортируем функцию для отображения главного меню
                from bot_modified import send_main_menu
                
                # Отправляем главное меню с возможностью генерации плана
                await send_main_menu(update, context, 
                    "Теперь вы можете получить персонализированный план тренировок, основанный на вашем профиле."
                )
            else:
                await update.message.reply_text(
                    "⚠️ Произошла ошибка при сохранении профиля. Пожалуйста, попробуйте позже.",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            return ConversationHandler.END
            
        elif text == 'Нет, начать заново':
            # Clear user data and restart
            context.user_data['profile_data'] = {}
            
            await update.message.reply_text(
                "Давайте начнем заново. Какую дистанцию бега вы планируете пробежать (в километрах)?",
                reply_markup=ReplyKeyboardRemove()
            )
            return STATES['DISTANCE']
            
        else:
            reply_markup = ReplyKeyboardMarkup(
                [['Да, сохранить мой профиль', 'Нет, начать заново']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, выберите 'Да, сохранить мой профиль' или 'Нет, начать заново'.",
                reply_markup=reply_markup
            )
            return STATES['CONFIRMATION']
    
    async def cancel(self, update: Update, context: CallbackContext):
        """Cancel the conversation."""
        await update.message.reply_text(
            "Создание профиля отменено. Вы можете начать снова в любое время.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Импортируем функцию для отображения главного меню
        from bot_modified import send_main_menu
        
        # Отправляем главное меню с возможностью вернуться к созданию профиля
        await send_main_menu(update, context, "Что бы вы хотели сделать дальше?")
        
        return ConversationHandler.END
    
    def get_conversation_handler(self):
        """Return the ConversationHandler with all states defined."""
        from telegram.ext import (
            CommandHandler, MessageHandler, filters, ConversationHandler
        )
        
        # Создаем основной обработчик создания профиля
        main_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                STATES['DISTANCE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_distance)],
                STATES['COMPETITION_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_competition_date)],
                STATES['GENDER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_gender)],
                STATES['AGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_age)],
                STATES['HEIGHT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_height)],
                STATES['WEIGHT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weight)],
                STATES['GOAL']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_goal)],
                STATES['TARGET_TIME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_target_time)],
                STATES['FITNESS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_fitness)],
                STATES['WEEKLY_VOLUME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weekly_volume)],
                STATES['TRAINING_START_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_training_start_date)],
                STATES['TRAINING_DAYS_PER_WEEK']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_training_days_per_week)],
                STATES['PREFERRED_TRAINING_DAYS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_preferred_training_days)],
                STATES['CONFIRMATION']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm_data)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            name="runner_profile_conversation",
            persistent=False,
        )
        
        # Создаем обработчик для обновления профиля
        # Используем тот же класс ConversationHandler для обоих случаев (создание и обновление)
        # Отличие только в том, что для обновления используется другая точка входа
        update_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex(r'^✏️ Обновить мой профиль$'), self.start_update)],
            states={
                STATES['DISTANCE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_distance)],
                STATES['COMPETITION_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_competition_date)],
                STATES['GENDER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_gender)],
                STATES['AGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_age)],
                STATES['HEIGHT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_height)],
                STATES['WEIGHT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weight)],
                STATES['GOAL']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_goal)],
                STATES['TARGET_TIME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_target_time)],
                STATES['FITNESS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_fitness)],
                STATES['WEEKLY_VOLUME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weekly_volume)],
                STATES['TRAINING_START_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_training_start_date)],
                STATES['TRAINING_DAYS_PER_WEEK']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_training_days_per_week)],
                STATES['PREFERRED_TRAINING_DAYS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_preferred_training_days)],
                STATES['CONFIRMATION']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm_data)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            name="update_profile_conversation",
            persistent=False,
        )
        
        return [main_handler, update_handler]

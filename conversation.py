from telegram import ReplyKeyboardMarkup, KeyboardButton, Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from datetime import datetime
import re

from config import STATES, logging
from db_manager import DBManager

class RunnerProfileConversation:
    """Manages the conversation flow for collecting runner profile information."""
    
    def __init__(self):
        """Initialize the conversation handler with empty profile data dict."""
        self.user_data = {}
    
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
            
            # Ask about running experience with keyboard
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
                "Каков ваш опыт бега?",
                reply_markup=reply_markup
            )
            return STATES['EXPERIENCE']
            
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
                ['10', '20'],
                ['30', '40'],
                ['50', '60'],
                ['70', '80']
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
        
        try:
            volume = float(text.replace(',', '.'))
            if volume < 0 or volume > 500:
                # Добавляем кнопки с вариантами объема при ошибке
                reply_markup = ReplyKeyboardMarkup(
                    [
                        ['10', '20'],
                        ['30', '40'],
                        ['50', '60'],
                        ['70', '80']
                    ],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                await update.message.reply_text(
                    "Пожалуйста, введите корректный еженедельный объем бега от 0 до 500 км.",
                    reply_markup=reply_markup
                )
                return STATES['WEEKLY_VOLUME']
            
            context.user_data['profile_data']['weekly_volume'] = volume
            
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
                f"⏱️ Опыт бега: {profile['experience']}\n"
                f"🎯 Цель: {profile['goal']}\n"
            )
            
            if profile['goal'] == 'Улучшить время':
                summary += f"⏱️ Целевое время: {profile['target_time']}\n"
                
            summary += (
                f"💪 Уровень физической подготовки: {profile['fitness_level']}\n"
                f"📊 Еженедельный объем: {profile['weekly_volume']} км\n\n"
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
            
        except ValueError:
            # Добавляем кнопки с вариантами объема при ошибке
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['10', '20'],
                    ['30', '40'],
                    ['50', '60'],
                    ['70', '80']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Пожалуйста, введите корректное числовое значение еженедельного объема бега в километрах.",
                reply_markup=reply_markup
            )
            return STATES['WEEKLY_VOLUME']
    
    async def confirm_data(self, update: Update, context: CallbackContext):
        """Handle user confirmation of collected data."""
        text = update.message.text.strip()
        
        if text == 'Да, сохранить мой профиль':
            user_id = context.user_data.get('db_user_id')
            profile_data = context.user_data.get('profile_data', {})
            
            # Save profile to database
            if DBManager.save_runner_profile(user_id, profile_data):
                await update.message.reply_text(
                    "🎉 Отлично! Ваш профиль бегуна успешно сохранен. "
                    "Спасибо за предоставленную информацию!",
                    reply_markup=ReplyKeyboardRemove()
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
            "Создание профиля отменено. Вы можете начать снова в любое время, отправив команду /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    def get_conversation_handler(self):
        """Return the ConversationHandler with all states defined."""
        from telegram.ext import (
            CommandHandler, MessageHandler, filters, ConversationHandler
        )
        
        return ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                STATES['DISTANCE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_distance)],
                STATES['COMPETITION_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_competition_date)],
                STATES['GENDER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_gender)],
                STATES['AGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_age)],
                STATES['HEIGHT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_height)],
                STATES['WEIGHT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weight)],
                STATES['EXPERIENCE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_experience)],
                STATES['GOAL']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_goal)],
                STATES['TARGET_TIME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_target_time)],
                STATES['FITNESS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_fitness)],
                STATES['WEEKLY_VOLUME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weekly_volume)],
                STATES['CONFIRMATION']: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm_data)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            name="runner_profile_conversation",
            persistent=False,
        )

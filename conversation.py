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
                "Sorry, there was an error starting the conversation. Please try again later."
            )
            return ConversationHandler.END
        
        # Store user_id in context.user_data
        context.user_data['db_user_id'] = user_id
        context.user_data['profile_data'] = {}
        
        await update.message.reply_text(
            f"Hi {user.first_name}! I'll help you create your runner profile. "
            "Let's start with some basic information about your running goals.\n\n"
            "What's your target running distance in kilometers?"
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
                    "Please enter a positive distance value."
                )
                return STATES['DISTANCE']
            
            context.user_data['profile_data']['distance'] = distance
            
            await update.message.reply_text(
                f"Great! You're planning to run {distance} km.\n\n"
                "When is your competition? Please enter the date in DD.MM.YYYY format."
            )
            return STATES['COMPETITION_DATE']
            
        except ValueError:
            await update.message.reply_text(
                "Please enter a valid numeric distance in kilometers."
            )
            return STATES['DISTANCE']
    
    async def collect_competition_date(self, update: Update, context: CallbackContext):
        """Collect and validate competition date."""
        text = update.message.text.strip()
        
        # Validate date format
        date_pattern = r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$'
        match = re.match(date_pattern, text)
        
        if not match:
            await update.message.reply_text(
                "Please enter the date in DD.MM.YYYY format (e.g., 25.12.2023)."
            )
            return STATES['COMPETITION_DATE']
        
        day, month, year = map(int, match.groups())
        
        try:
            date_obj = datetime(year, month, day)
            today = datetime.now()
            
            if date_obj < today:
                await update.message.reply_text(
                    "The competition date should be in the future. Please enter a valid date."
                )
                return STATES['COMPETITION_DATE']
            
            context.user_data['profile_data']['competition_date'] = text
            
            # Ask for gender with keyboard
            reply_markup = ReplyKeyboardMarkup(
                [['Male', 'Female']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "What is your gender?",
                reply_markup=reply_markup
            )
            return STATES['GENDER']
            
        except ValueError:
            await update.message.reply_text(
                "Please enter a valid date in DD.MM.YYYY format."
            )
            return STATES['COMPETITION_DATE']
    
    async def collect_gender(self, update: Update, context: CallbackContext):
        """Collect gender information."""
        text = update.message.text.strip()
        
        if text not in ['Male', 'Female']:
            reply_markup = ReplyKeyboardMarkup(
                [['Male', 'Female']], 
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Please select 'Male' or 'Female'.",
                reply_markup=reply_markup
            )
            return STATES['GENDER']
        
        context.user_data['profile_data']['gender'] = text
        
        await update.message.reply_text(
            "What is your age?",
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
                    "Please enter a valid age between 10 and 120 years."
                )
                return STATES['AGE']
            
            context.user_data['profile_data']['age'] = age
            
            await update.message.reply_text(
                "What is your height in centimeters?"
            )
            return STATES['HEIGHT']
            
        except ValueError:
            await update.message.reply_text(
                "Please enter your age as a whole number."
            )
            return STATES['AGE']
    
    async def collect_height(self, update: Update, context: CallbackContext):
        """Collect and validate height."""
        text = update.message.text.strip()
        
        try:
            height = float(text.replace(',', '.'))
            if height < 100 or height > 250:
                await update.message.reply_text(
                    "Please enter a valid height between 100 and 250 cm."
                )
                return STATES['HEIGHT']
            
            context.user_data['profile_data']['height'] = height
            
            await update.message.reply_text(
                "What is your weight in kilograms?"
            )
            return STATES['WEIGHT']
            
        except ValueError:
            await update.message.reply_text(
                "Please enter a valid numeric height in centimeters."
            )
            return STATES['HEIGHT']
    
    async def collect_weight(self, update: Update, context: CallbackContext):
        """Collect and validate weight."""
        text = update.message.text.strip()
        
        try:
            weight = float(text.replace(',', '.'))
            if weight < 30 or weight > 250:
                await update.message.reply_text(
                    "Please enter a valid weight between 30 and 250 kg."
                )
                return STATES['WEIGHT']
            
            context.user_data['profile_data']['weight'] = weight
            
            # Ask about running experience with keyboard
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Complete beginner'],
                    ['Less than 1 year'],
                    ['1-3 years'],
                    ['3-5 years'],
                    ['More than 5 years']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "What is your running experience?",
                reply_markup=reply_markup
            )
            return STATES['EXPERIENCE']
            
        except ValueError:
            await update.message.reply_text(
                "Please enter a valid numeric weight in kilograms."
            )
            return STATES['WEIGHT']
    
    async def collect_experience(self, update: Update, context: CallbackContext):
        """Collect running experience."""
        text = update.message.text.strip()
        valid_experiences = [
            'Complete beginner',
            'Less than 1 year',
            '1-3 years',
            '3-5 years',
            'More than 5 years'
        ]
        
        if text not in valid_experiences:
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Complete beginner'],
                    ['Less than 1 year'],
                    ['1-3 years'],
                    ['3-5 years'],
                    ['More than 5 years']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Please select one of the provided options.",
                reply_markup=reply_markup
            )
            return STATES['EXPERIENCE']
        
        context.user_data['profile_data']['experience'] = text
        
        # Ask about running goal
        reply_markup = ReplyKeyboardMarkup(
            [['Just finish', 'Improve time']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "What is your goal for this run?",
            reply_markup=reply_markup
        )
        return STATES['GOAL']
    
    async def collect_goal(self, update: Update, context: CallbackContext):
        """Collect runner's goal."""
        text = update.message.text.strip()
        
        if text not in ['Just finish', 'Improve time']:
            reply_markup = ReplyKeyboardMarkup(
                [['Just finish', 'Improve time']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Please select 'Just finish' or 'Improve time'.",
                reply_markup=reply_markup
            )
            return STATES['GOAL']
        
        context.user_data['profile_data']['goal'] = text
        
        if text == 'Improve time':
            await update.message.reply_text(
                "What is your target finish time? Please enter in format HH:MM:SS",
                reply_markup=ReplyKeyboardRemove()
            )
            return STATES['TARGET_TIME']
        else:
            # Skip target time question for 'Just finish' goal
            context.user_data['profile_data']['target_time'] = 'N/A'
            
            # Ask about fitness level
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Beginner'],
                    ['Intermediate'],
                    ['Advanced'],
                    ['Elite']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "How would you rate your physical fitness level?",
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
                "Please enter time in format HH:MM or HH:MM:SS (e.g., 01:30:00)"
            )
            return STATES['TARGET_TIME']
        
        context.user_data['profile_data']['target_time'] = text
        
        # Ask about fitness level
        reply_markup = ReplyKeyboardMarkup(
            [
                ['Beginner'],
                ['Intermediate'],
                ['Advanced'],
                ['Elite']
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "How would you rate your physical fitness level?",
            reply_markup=reply_markup
        )
        return STATES['FITNESS']
    
    async def collect_fitness(self, update: Update, context: CallbackContext):
        """Collect fitness level."""
        text = update.message.text.strip()
        valid_levels = ['Beginner', 'Intermediate', 'Advanced', 'Elite']
        
        if text not in valid_levels:
            reply_markup = ReplyKeyboardMarkup(
                [
                    ['Beginner'],
                    ['Intermediate'],
                    ['Advanced'],
                    ['Elite']
                ],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Please select one of the provided fitness levels.",
                reply_markup=reply_markup
            )
            return STATES['FITNESS']
        
        context.user_data['profile_data']['fitness_level'] = text
        
        await update.message.reply_text(
            "What is your current weekly running volume in kilometers?",
            reply_markup=ReplyKeyboardRemove()
        )
        return STATES['WEEKLY_VOLUME']
    
    async def collect_weekly_volume(self, update: Update, context: CallbackContext):
        """Collect and validate weekly running volume."""
        text = update.message.text.strip()
        
        try:
            volume = float(text.replace(',', '.'))
            if volume < 0 or volume > 500:
                await update.message.reply_text(
                    "Please enter a valid weekly volume between 0 and 500 km."
                )
                return STATES['WEEKLY_VOLUME']
            
            context.user_data['profile_data']['weekly_volume'] = volume
            
            # Display summary of collected information
            profile = context.user_data['profile_data']
            summary = (
                "Great! Here's a summary of your runner profile:\n\n"
                f"🏃 Target distance: {profile['distance']} km\n"
                f"📅 Competition date: {profile['competition_date']}\n"
                f"👤 Gender: {profile['gender']}\n"
                f"🎂 Age: {profile['age']}\n"
                f"📏 Height: {profile['height']} cm\n"
                f"⚖️ Weight: {profile['weight']} kg\n"
                f"⏱️ Running experience: {profile['experience']}\n"
                f"🎯 Goal: {profile['goal']}\n"
            )
            
            if profile['goal'] == 'Improve time':
                summary += f"⏱️ Target time: {profile['target_time']}\n"
                
            summary += (
                f"💪 Fitness level: {profile['fitness_level']}\n"
                f"📊 Weekly volume: {profile['weekly_volume']} km\n\n"
                "Is this information correct?"
            )
            
            reply_markup = ReplyKeyboardMarkup(
                [['Yes, save my profile', 'No, start over']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                summary,
                reply_markup=reply_markup
            )
            return STATES['CONFIRMATION']
            
        except ValueError:
            await update.message.reply_text(
                "Please enter a valid numeric weekly volume in kilometers."
            )
            return STATES['WEEKLY_VOLUME']
    
    async def confirm_data(self, update: Update, context: CallbackContext):
        """Handle user confirmation of collected data."""
        text = update.message.text.strip()
        
        if text == 'Yes, save my profile':
            user_id = context.user_data.get('db_user_id')
            profile_data = context.user_data.get('profile_data', {})
            
            # Save profile to database
            if DBManager.save_runner_profile(user_id, profile_data):
                await update.message.reply_text(
                    "🎉 Perfect! Your runner profile has been saved successfully. "
                    "Thank you for providing this information!",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "⚠️ There was an error saving your profile. Please try again later.",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            return ConversationHandler.END
            
        elif text == 'No, start over':
            # Clear user data and restart
            context.user_data['profile_data'] = {}
            
            await update.message.reply_text(
                "Let's start over. What's your target running distance in kilometers?",
                reply_markup=ReplyKeyboardRemove()
            )
            return STATES['DISTANCE']
            
        else:
            reply_markup = ReplyKeyboardMarkup(
                [['Yes, save my profile', 'No, start over']],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Please select 'Yes, save my profile' or 'No, start over'.",
                reply_markup=reply_markup
            )
            return STATES['CONFIRMATION']
    
    async def cancel(self, update: Update, context: CallbackContext):
        """Cancel the conversation."""
        await update.message.reply_text(
            "Profile creation canceled. You can start again anytime by sending /start.",
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

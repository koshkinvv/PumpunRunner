import os
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Telegram Bot Token - should be added to environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# PostgreSQL Database Configuration
DB_CONFIG = {
    'host': os.environ.get("PGHOST"),
    'port': os.environ.get("PGPORT"),
    'dbname': os.environ.get("PGDATABASE"),
    'user': os.environ.get("PGUSER"),
    'password': os.environ.get("PGPASSWORD")
}

# Database URL for SQLAlchemy
DATABASE_URL = os.environ.get("DATABASE_URL")

# Define conversation states for the questionnaire
STATES = {
    'START': 0,
    'DISTANCE': 1,
    'COMPETITION_DATE': 2,
    'GENDER': 3,
    'AGE': 4,
    'HEIGHT': 5,
    'WEIGHT': 6,
    'EXPERIENCE': 7,
    'GOAL': 8,
    'TARGET_TIME': 9,
    'FITNESS': 10,
    'WEEKLY_VOLUME': 11,
    'CONFIRMATION': 12
}

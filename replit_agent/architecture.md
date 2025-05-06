# Architecture Documentation

## Overview

The Runner Profile Bot is a Telegram-based application that helps runners create personalized training plans. It leverages AI through OpenAI's GPT-4o model to generate customized running schedules based on user profiles and goals. The application consists of a Telegram bot interface combined with a web application, backed by a PostgreSQL database for persistent storage.

The system is designed to run as a background service on Replit's Reserved VM, with mechanisms in place to ensure continuous operation through health checks and automatic restarts.

## System Architecture

The application follows a multi-tier architecture with the following components:

1. **User Interface Layer**:
   - Telegram Bot: Primary interface for users to interact with the system
   - Web Interface: Simple Flask-based UI that provides status information and system health

2. **Application Layer**:
   - Bot Logic: Handles conversations, commands, and user interactions
   - Training Plan Generation: Creates personalized training plans using AI
   - Reminder System: Sends scheduled notifications about upcoming workouts
   - Image Analysis: Processes screenshots of workout activities

3. **Data Layer**:
   - PostgreSQL Database: Stores user profiles, training plans, and workout logs
   - File-based Health Monitoring: Tracks system uptime and process health

4. **Infrastructure Layer**:
   - Replit Reserved VM: Hosting environment for the application
   - Background Worker: Ensures the bot runs continuously

## Key Components

### Telegram Bot

The core of the application is implemented as a Telegram bot using the `python-telegram-bot` library. The bot uses conversation handlers to guide users through the process of creating a runner profile and generating training plans.

Key files:
- `bot_modified.py`: Main bot implementation with command handlers and conversation flow
- `conversation.py`: Manages the structured dialog for collecting user information
- `main.py`: Entry point that initializes and runs the bot application

The bot implements several commands:
- `/plan`: Create or view training plans
- `/pending`: Show pending (incomplete) workouts
- `/help`: Display available commands and information

### AI Integration

The application uses OpenAI's GPT-4o model to generate personalized training plans based on runner profiles.

Key files:
- `openai_service.py`: Handles communication with the OpenAI API
- `image_analyzer.py`: Uses AI to analyze workout screenshots

The AI service takes into account various factors from the user's profile:
- Distance goals
- Competition date
- Personal details (gender, age, height, weight)
- Experience level
- Weekly volume
- Preferred training days

### Database Management

The application uses PostgreSQL for data persistence, with several key tables:
- `users`: Stores basic user information
- `runner_profiles`: Contains detailed runner information and preferences
- `training_plans`: Stores generated training plans
- Associated tables for tracking workout completions and cancellations

Key files:
- `db_manager.py`: General database operations
- `training_plan_manager.py`: Specific operations for training plans
- `models.py`: Database schema definitions and utility functions

### Web Application

A simple Flask web application provides system status and a basic UI.

Key files:
- `app.py`: Flask application setup and routes
- `templates/index.html`: Main page template
- `wsgi.py`: WSGI entry point for Gunicorn

### Health Monitoring

The application includes multiple components for ensuring continuous operation:

Key files:
- `bot_health_monitor.py`: Monitors bot health and restarts if necessary
- `bot_monitor.py`: Core monitoring functionality
- Various launcher scripts: Different approaches for starting and managing the bot

## Data Flow

1. **User Registration/Profile Creation**:
   - User initiates conversation with the bot
   - Bot collects profile information through a guided conversation
   - Profile data is stored in PostgreSQL

2. **Training Plan Generation**:
   - User requests a training plan
   - System retrieves user profile from the database
   - Profile is sent to OpenAI API for plan generation
   - Generated plan is stored in the database and presented to the user

3. **Workout Tracking**:
   - User marks workouts as completed or canceled
   - System tracks progress and accumulates metrics
   - Analytics can be viewed through bot commands

4. **Image Analysis**:
   - User uploads screenshot from fitness tracker app
   - System uses AI to extract workout details
   - Extracted data is used to automatically record workout completion

5. **Reminders**:
   - System checks for upcoming workouts daily
   - Notifications are sent to users about the next day's workout

## External Dependencies

The application relies on several external services and libraries:

1. **OpenAI API**: Used for generating training plans and analyzing screenshots
   - Model: GPT-4o
   - Integration via the OpenAI Python client

2. **Telegram Bot API**: Primary user interface
   - Integration via `python-telegram-bot` library

3. **PostgreSQL**: Data persistence
   - Accessed via `psycopg2` and SQLAlchemy

4. **Flask**: Web interface
   - Used with Flask-SQLAlchemy for database integration

5. **Gunicorn**: WSGI HTTP server for the web interface

## Deployment Strategy

The application is designed to run on Replit's Reserved VM as a Background Worker. This approach ensures the bot runs continuously without the limitations of regular Replit instances.

### Deployment Components:

1. **Bot Runner**: Various scripts to maintain bot uptime
   - `deploy_bot.py`: Primary deployment script
   - `bot_service.py`: Service wrapper for continuous operation
   - `clean_start.py`, `start_bot_directly.py`: Alternative launchers for different scenarios

2. **Process Management**:
   - Health checks via file-based timestamps
   - Automatic detection and termination of conflicting processes
   - Restart mechanisms when failures occur

3. **API Session Management**:
   - Strategies to handle the Telegram API's "one bot instance" constraint
   - Session cleanup and reset functionality

4. **Web Server**:
   - Gunicorn serves the Flask application
   - Configured to handle multiple worker processes

### Reliability Mechanisms:

1. **Health Monitoring**:
   - Regular updates to health check files
   - Background process that verifies bot operation
   - Automatic restart of failed components

2. **Conflict Resolution**:
   - Detection and resolution of multiple bot instances
   - API session reset to prevent "Conflict: terminated by other getUpdates request" errors

3. **Logging**:
   - Comprehensive logging system for debugging
   - Separate log files for different components

## Scaling Considerations

The current architecture is designed for relatively modest scale (hundreds to low thousands of users). For larger scale deployments, several modifications would be recommended:

1. Separating the web application and bot into distinct services
2. Implementing a queue system for distributing message processing
3. Optimizing database access patterns and implementing caching
4. Migrating from a single VM to a containerized approach
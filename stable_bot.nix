# Конфигурация для стабильного запуска бота
# Этот файл нужно подключить в Replit вручную

{
  # Используем наш улучшенный скрипт для запуска бота
  startup_script = "python3 run_fixed_bot.py";
  
  # Определяем зависимости
  packages = [
    "python3"
    "postgresql-16"
  ];
  
  # Переменные окружения
  env = {
    PYTHONPATH = "$PYTHONPATH:$HOME/workspace";
    PATH = "$PATH:$HOME/workspace/.pythonlibs/bin";
  };
}
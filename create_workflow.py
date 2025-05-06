"""
Скрипт для настройки workflow запуска веб-приложения.
"""
import os
import subprocess
import sys

def main():
    """Основная функция для настройки workflow."""
    # Создаем скрипт запуска
    runner_script = """#!/bin/bash
python run_updated_webapp.py
"""
    
    with open("web_runner.sh", "w") as f:
        f.write(runner_script)
    
    # Делаем скрипт исполняемым
    os.chmod("web_runner.sh", 0o755)
    
    print("Скрипт запуска веб-приложения создан: web_runner.sh")
    print("Теперь вы можете запустить его командой: python run_updated_webapp.py")
    print("или: ./web_runner.sh")

if __name__ == "__main__":
    main()
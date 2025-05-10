#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для настройки и запуска workflow с улучшенным форматированием тренировок.
"""

import os
import subprocess
import sys

def create_workflow_file():
    """Создает файл конфигурации workflow для улучшенного бота."""
    workflow_content = """
[nix]
channel = "stable-23_11"

[deployment]
run = ["sh", "-c", "./run_improved_bot.sh"]
ignorePorts = false

[[ports]]
localPort = 3000
externalPort = 80
"""
    try:
        with open(".replit.workflow", "w") as f:
            f.write(workflow_content.strip())
        print("Файл конфигурации workflow успешно создан.")
        return True
    except Exception as e:
        print(f"Ошибка при создании файла конфигурации workflow: {e}")
        return False

def setup_workflow():
    """Настраивает и запускает workflow для улучшенного бота."""
    try:
        # Создаем файл конфигурации
        if not create_workflow_file():
            return False
        
        # Перезапускаем workflow
        print("Перезапускаем workflow...")
        subprocess.run(["replit", "workflow", "restart"], check=True)
        
        print("Workflow успешно настроен и перезапущен.")
        return True
    except Exception as e:
        print(f"Ошибка при настройке workflow: {e}")
        return False

if __name__ == "__main__":
    if setup_workflow():
        print("Бот с улучшенным форматированием тренировок запущен и готов к использованию.")
        sys.exit(0)
    else:
        print("Не удалось настроить и запустить бота. Проверьте логи для подробностей.")
        sys.exit(1)
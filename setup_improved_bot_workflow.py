#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для настройки workflow для бота с улучшенным форматированием тренировок.
Создает необходимые файлы конфигурации и запускает workflow.
"""

import os
import json
import sys
import subprocess
import time
from datetime import datetime

def create_workflow_config():
    """Создает файл конфигурации workflow."""
    config = {
        "name": "improved_bot",
        "onBoot": True,
        "cache": True,
        "persistent": True,
        "restartAt": {"hours": 3, "minutes": 0},
        "replFile": "start_improved_bot.py",
        "language": "python",
        "run": "bash run_improved_bot.sh"
    }
    
    try:
        with open(".replit.workflow", "w") as f:
            f.write(json.dumps(config, indent=2))
        print("Файл конфигурации workflow успешно создан")
        return True
    except Exception as e:
        print(f"Ошибка при создании файла конфигурации workflow: {e}")
        return False

def create_nix_config():
    """Создает файл конфигурации nix для стабильного запуска."""
    nix_config = """
{ pkgs }: {
  deps = [
    pkgs.python311Full
    pkgs.pip
    pkgs.replitPackages.prybar-python311
    pkgs.replitPackages.stderred
  ];
  env = {
    PYTHON_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib
      pkgs.zlib
      pkgs.glib
      pkgs.xorg.libX11
    ];
    PYTHONHOME = "${pkgs.python311Full}";
    PYTHONBIN = "${pkgs.python311Full}/bin/python3.11";
    LANG = "en_US.UTF-8";
    STDERREDBIN = "${pkgs.replitPackages.stderred}/bin/stderred";
    PRYBAR_PYTHON_BIN = "${pkgs.replitPackages.prybar-python311}/bin/prybar-python311";
  };
}
"""
    
    try:
        with open("stable_improved_bot.nix", "w") as f:
            f.write(nix_config.strip())
        print("Файл конфигурации nix успешно создан")
        return True
    except Exception as e:
        print(f"Ошибка при создании файла конфигурации nix: {e}")
        return False

def restart_workflow():
    """Перезапускает workflow."""
    try:
        result = subprocess.run(
            ["replit", "workflow", "restart"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            print("Workflow успешно перезапущен")
            return True
        else:
            print(f"Ошибка при перезапуске workflow: {result.stderr}")
            return False
    except Exception as e:
        print(f"Исключение при перезапуске workflow: {e}")
        return False

def create_bot_health_file():
    """Создает файл для проверки здоровья бота."""
    try:
        with open("bot_health.txt", "w") as f:
            f.write(str(int(time.time())))
        print("Файл проверки здоровья бота создан")
        return True
    except Exception as e:
        print(f"Ошибка при создании файла проверки здоровья: {e}")
        return False

def main():
    """Основная функция для настройки workflow."""
    print(f"Настройка workflow для бота с улучшенным форматированием тренировок ({datetime.now()})")
    
    # Проверяем, что все необходимые файлы существуют
    if not os.path.exists("improved_training_format.py"):
        print("Ошибка: файл improved_training_format.py не найден")
        return False
    
    if not os.path.exists("start_improved_bot.py"):
        print("Ошибка: файл start_improved_bot.py не найден")
        return False
    
    if not os.path.exists("run_improved_bot.sh"):
        print("Ошибка: файл run_improved_bot.sh не найден")
        return False
    
    # Делаем скрипт запуска исполняемым
    try:
        os.chmod("run_improved_bot.sh", 0o755)
        print("Права на запуск run_improved_bot.sh установлены")
    except Exception as e:
        print(f"Ошибка при установке прав на запуск скрипта: {e}")
        return False
    
    # Создаем конфигурационные файлы
    if not create_workflow_config():
        return False
    
    if not create_nix_config():
        return False
    
    if not create_bot_health_file():
        return False
    
    # Перезапускаем workflow
    if not restart_workflow():
        return False
    
    print("Настройка workflow завершена успешно")
    print("Бот с улучшенным форматированием тренировок будет запущен автоматически")
    return True

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        print("Ошибка при настройке workflow")
        sys.exit(1)
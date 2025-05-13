#!/usr/bin/env python3
"""
Скрипт для создания рабочего процесса лендинга
"""
import os
import json
import subprocess

def create_workflow():
    """
    Создает файл конфигурации рабочего процесса для лендинга
    """
    # Создаем контент для файла .replit.workflow
    workflow_content = """[landing]
run = ["python3", "run_webapp.py"]
language = "python3"
persistent_folder = "."
"""
    
    # Записываем его в файл
    with open(".replit.workflow", "w") as f:
        f.write(workflow_content)
    
    print("Рабочий процесс успешно создан")
    
if __name__ == "__main__":
    create_workflow()
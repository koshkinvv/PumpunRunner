#!/usr/bin/env python3
"""
Консольный интерфейс для работы с OpenAI API.
Позволяет отправлять запросы к API OpenAI из командной строки.
"""
import os
import sys
import json
import argparse
from openai import OpenAI

# Настройка цветов для вывода в терминал
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def get_api_key():
    """Получение API ключа OpenAI из переменных окружения"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(f"{Colors.FAIL}Ошибка: Не найден OPENAI_API_KEY в переменных окружения.{Colors.ENDC}")
        print(f"{Colors.WARNING}Пожалуйста, установите OPENAI_API_KEY в переменных окружения.{Colors.ENDC}")
        sys.exit(1)
    return api_key

def chat_completion(prompt, model="gpt-4o", temperature=0.7, max_tokens=1000, json_mode=False):
    """Отправка запроса к Chat Completion API"""
    client = OpenAI(api_key=get_api_key())
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        if json_mode:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        
        return response
    except Exception as e:
        print(f"{Colors.FAIL}Ошибка при запросе к OpenAI API: {e}{Colors.ENDC}")
        sys.exit(1)

def test_api_connection():
    """Тестирование соединения с API OpenAI"""
    client = OpenAI(api_key=get_api_key())
    
    try:
        models = client.models.list()
        print(f"{Colors.GREEN}Соединение с OpenAI API успешно установлено!{Colors.ENDC}")
        print(f"\n{Colors.CYAN}Доступные модели:{Colors.ENDC}")
        
        # Вывод списка моделей
        for model in models.data:
            print(f"- {model.id}")
        
        return True
    except Exception as e:
        print(f"{Colors.FAIL}Ошибка при подключении к OpenAI API: {e}{Colors.ENDC}")
        return False

def format_response(response, json_output=False):
    """Форматирование ответа от API"""
    content = response.choices[0].message.content
    
    if json_output:
        try:
            # Попытка форматирования JSON-ответа
            parsed = json.loads(content)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except:
            # Если не удалось разобрать как JSON, возвращаем как есть
            return content
    
    return content

def main():
    """Основная функция CLI интерфейса"""
    parser = argparse.ArgumentParser(description="OpenAI API CLI интерфейс")
    
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    
    # Команда test
    test_parser = subparsers.add_parser("test", help="Тестирование соединения с API")
    
    # Команда chat
    chat_parser = subparsers.add_parser("chat", help="Отправить запрос к Chat Completion API")
    chat_parser.add_argument("prompt", help="Запрос к модели")
    chat_parser.add_argument("--model", default="gpt-4o", help="Название модели (по умолчанию: gpt-4o)")
    chat_parser.add_argument("--temperature", type=float, default=0.7, help="Температура (0.0-2.0)")
    chat_parser.add_argument("--max-tokens", type=int, default=1000, help="Максимальное количество токенов ответа")
    chat_parser.add_argument("--json", action="store_true", help="Запросить ответ в формате JSON")
    chat_parser.add_argument("--output-json", action="store_true", help="Форматировать вывод как JSON")
    
    args = parser.parse_args()
    
    # Обработка команд
    if args.command == "test":
        test_api_connection()
    
    elif args.command == "chat":
        print(f"{Colors.CYAN}Отправка запроса к модели {args.model}...{Colors.ENDC}")
        response = chat_completion(
            args.prompt, 
            model=args.model, 
            temperature=args.temperature, 
            max_tokens=args.max_tokens,
            json_mode=args.json
        )
        
        print(f"\n{Colors.GREEN}Ответ:{Colors.ENDC}")
        print(format_response(response, json_output=args.output_json))
        
        # Дополнительная информация о запросе
        print(f"\n{Colors.BLUE}Информация о запросе:{Colors.ENDC}")
        print(f"- Модель: {response.model}")
        print(f"- Токены запроса: {response.usage.prompt_tokens}")
        print(f"- Токены ответа: {response.usage.completion_tokens}")
        print(f"- Всего токенов: {response.usage.total_tokens}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
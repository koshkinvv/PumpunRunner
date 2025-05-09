#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к OpenAI API.
Проверяет доступность сервиса, настройки API ключа и список доступных моделей.
"""
import os
import json
import argparse
from openai import OpenAI

def test_api():
    """Проверка соединения с OpenAI API"""
    print("Тестирование подключения к OpenAI API...")
    
    # Проверяем наличие API ключа в переменных окружения
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ Ошибка: API ключ OpenAI не найден!")
        print("Пожалуйста, убедитесь, что переменная окружения OPENAI_API_KEY установлена.")
        return False
    
    # Проверяем, не является ли API ключ пустым или некорректным
    if len(api_key) < 20:
        print("\n❌ Ошибка: API ключ OpenAI некорректен!")
        print("API ключ слишком короткий или имеет неверный формат.")
        return False
    
    # Создаем клиент OpenAI
    client = OpenAI(api_key=api_key)
    
    try:
        # Пробуем получить список моделей
        models = client.models.list()
        print("\n✅ Соединение с OpenAI API успешно установлено!")
        
        # Выводим список доступных моделей
        print("\nДоступные модели:")
        for model in models.data:
            print(f"- {model.id}")
        
        # Проверяем наличие GPT-4o среди доступных моделей
        gpt4o_available = any(model.id == "gpt-4o" for model in models.data)
        if gpt4o_available:
            print("\n✅ Модель gpt-4o доступна.")
        else:
            print("\n⚠️ Модель gpt-4o не найдена среди доступных моделей.")
            print("Возможно, у вас нет доступа к этой модели.")
        
        # Проверяем наличие GPT-4 среди доступных моделей
        gpt4_available = any(model.id.startswith("gpt-4") for model in models.data)
        if gpt4_available:
            print("✅ Модели семейства GPT-4 доступны.")
        else:
            print("⚠️ Модели семейства GPT-4 не найдены среди доступных моделей.")
            print("Возможно, у вас нет доступа к этим моделям.")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Ошибка при подключении к API: {e}")
        
        # Предложения по исправлению типичных ошибок
        if "Authentication" in str(e):
            print("\nВозможные причины ошибки:")
            print("1. Неверный или недействительный API ключ")
            print("2. API ключ не активирован или отозван")
            print("3. У API ключа закончились средства")
            print("\nРешение:")
            print("- Проверьте правильность API ключа")
            print("- Создайте новый ключ на странице https://platform.openai.com/api-keys")
        
        return False

def test_simple_request():
    """Выполняет простой тестовый запрос к API"""
    print("\nВыполнение тестового запроса к API...")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ Нет API ключа для выполнения запроса.")
        return False
    
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Используем более доступную модель для теста
            messages=[
                {"role": "system", "content": "Ты простой тестовый ассистент."},
                {"role": "user", "content": "Скажи 'Тест успешно пройден!'."}
            ],
            max_tokens=20
        )
        
        # Выводим ответ
        content = response.choices[0].message.content.strip()
        print(f"\n✅ Тестовый запрос выполнен успешно!")
        print(f"Ответ от API: \"{content}\"")
        
        # Выводим информацию о токенах
        print(f"\nИнформация о запросе:")
        print(f"- Использованная модель: {response.model}")
        print(f"- Токены запроса: {response.usage.prompt_tokens}")
        print(f"- Токены ответа: {response.usage.completion_tokens}")
        print(f"- Всего токенов: {response.usage.total_tokens}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестового запроса: {e}")
        return False

def main():
    """Основная функция тестирования API"""
    parser = argparse.ArgumentParser(description="Тестирование OpenAI API")
    parser.add_argument("--full", action="store_true", help="Выполнить полное тестирование, включая тестовый запрос")
    args = parser.parse_args()
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К OPENAI API")
    print("=" * 60)
    
    connection_ok = test_api()
    
    if connection_ok and args.full:
        test_simple_request()
    
    print("\n" + "=" * 60)
    if connection_ok:
        print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО")
    else:
        print("❌ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО С ОШИБКАМИ")
    print("=" * 60)

if __name__ == "__main__":
    main()
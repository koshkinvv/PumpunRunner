#!/usr/bin/env python3
"""
Скрипт для тестирования набора данных JSONL с промптами для тренировки модели OpenAI.
Позволяет анализировать файл с промптами и проверять их качество.
"""
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/jsonl_dataset_test.log')
    ]
)
logger = logging.getLogger("jsonl_dataset_test")

# Получаем API ключ OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4o"

class JSONLDatasetAnalyzer:
    """Класс для анализа и тестирования наборов данных JSONL."""
    
    def __init__(self, file_path: str):
        """
        Инициализация анализатора набора данных.
        
        Args:
            file_path: Путь к JSONL файлу с промптами
        """
        self.file_path = file_path
        self.examples = []
        self.unique_system_prompts = set()
        self.unique_user_prompts = set()
        self.unique_assistant_prompts = set()
        
        if OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            self.client = None
            logger.warning("OPENAI_API_KEY не установлен. Функции тестирования с API будут недоступны.")
    
    def load_data(self) -> bool:
        """
        Загружает данные из JSONL файла.
        
        Returns:
            bool: True, если загрузка успешна, иначе False
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                    
                try:
                    data = json.loads(line)
                    self.examples.append(data)
                    
                    # Анализируем сообщения
                    messages = data.get('messages', [])
                    
                    for msg in messages:
                        role = msg.get('role', '')
                        content = msg.get('content', '')
                        
                        if role == 'system':
                            self.unique_system_prompts.add(content)
                        elif role == 'user':
                            self.unique_user_prompts.add(content)
                        elif role == 'assistant':
                            self.unique_assistant_prompts.add(content)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON в строке {i}: {e}")
            
            logger.info(f"Загружено {len(self.examples)} примеров из файла {self.file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных из файла {self.file_path}: {e}")
            return False
    
    def analyze_dataset(self) -> Dict[str, Any]:
        """
        Анализирует загруженный набор данных.
        
        Returns:
            Dict: Словарь с результатами анализа
        """
        if not self.examples:
            logger.warning("Нет загруженных данных для анализа")
            return {}
        
        # Базовая статистика
        stats = {
            "total_examples": len(self.examples),
            "unique_system_prompts": len(self.unique_system_prompts),
            "unique_user_prompts": len(self.unique_user_prompts),
            "unique_assistant_prompts": len(self.unique_assistant_prompts),
            "duplicates": self._find_duplicates(),
            "format_errors": self._check_format_errors(),
        }
        
        # Анализ разнообразия данных
        if len(self.unique_assistant_prompts) < len(self.examples) * 0.5:
            stats["diversity_warning"] = (
                f"Низкое разнообразие ответов ассистента: {len(self.unique_assistant_prompts)} "
                f"уникальных ответов на {len(self.examples)} примеров."
            )
        
        # Анализ форматирования
        stats["examples_by_structure"] = self._analyze_example_structures()
        
        return stats
    
    def _find_duplicates(self) -> Dict[str, Any]:
        """
        Находит дубликаты в наборе данных.
        
        Returns:
            Dict: Информация о дубликатах
        """
        duplicates = {
            "user_prompts": {},
            "assistant_responses": {},
            "full_examples": {}
        }
        
        # Проверка дубликатов пользовательских запросов
        user_prompts_count = {}
        for i, example in enumerate(self.examples):
            messages = example.get('messages', [])
            for msg in messages:
                if msg.get('role') == 'user':
                    content = msg.get('content', '')
                    if content in user_prompts_count:
                        user_prompts_count[content].append(i)
                    else:
                        user_prompts_count[content] = [i]
        
        # Фильтрация только дубликатов
        duplicates["user_prompts"] = {
            prompt: indices for prompt, indices in user_prompts_count.items() 
            if len(indices) > 1
        }
        
        # Аналогично для ответов ассистента
        assistant_responses_count = {}
        for i, example in enumerate(self.examples):
            messages = example.get('messages', [])
            for msg in messages:
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    if content in assistant_responses_count:
                        assistant_responses_count[content].append(i)
                    else:
                        assistant_responses_count[content] = [i]
        
        duplicates["assistant_responses"] = {
            response: indices for response, indices in assistant_responses_count.items() 
            if len(indices) > 1
        }
        
        return duplicates
    
    def _check_format_errors(self) -> List[Dict[str, Any]]:
        """
        Проверяет форматы сообщений на ошибки.
        
        Returns:
            List: Список ошибок форматирования
        """
        errors = []
        
        for i, example in enumerate(self.examples):
            messages = example.get('messages', [])
            
            # Проверка наличия всех необходимых ролей
            roles = [msg.get('role') for msg in messages]
            if 'system' not in roles:
                errors.append({"example_index": i, "error": "Отсутствует системное сообщение"})
            if 'user' not in roles:
                errors.append({"example_index": i, "error": "Отсутствует сообщение пользователя"})
            if 'assistant' not in roles:
                errors.append({"example_index": i, "error": "Отсутствует ответ ассистента"})
            
            # Проверка порядка сообщений
            for j, msg in enumerate(messages):
                role = msg.get('role')
                
                # Правильный порядок: system -> user -> assistant
                if j == 0 and role != 'system':
                    errors.append({"example_index": i, "error": f"Первое сообщение должно быть 'system', а не '{role}'"})
                
                if j == 1 and role != 'user':
                    errors.append({"example_index": i, "error": f"Второе сообщение должно быть 'user', а не '{role}'"})
                    
                if j == 2 and role != 'assistant':
                    errors.append({"example_index": i, "error": f"Третье сообщение должно быть 'assistant', а не '{role}'"})
                
                # Проверка пустых сообщений
                if not msg.get('content', '').strip():
                    errors.append({"example_index": i, "error": f"Пустое содержимое в сообщении с ролью '{role}'"})
        
        return errors
    
    def _analyze_example_structures(self) -> Dict[str, int]:
        """
        Анализирует структуры примеров в наборе данных.
        
        Returns:
            Dict: Словарь с количеством примеров для каждой структуры
        """
        structures = {}
        
        for example in self.examples:
            messages = example.get('messages', [])
            structure = tuple(msg.get('role') for msg in messages)
            
            if structure in structures:
                structures[structure] += 1
            else:
                structures[structure] = 1
        
        # Преобразуем кортежи в строки для удобства просмотра
        return {
            " -> ".join(struct): count 
            for struct, count in structures.items()
        }
    
    def test_with_api(self, num_examples: int = 1) -> List[Dict[str, Any]]:
        """
        Тестирует несколько примеров с использованием OpenAI API.
        
        Args:
            num_examples: Количество примеров для тестирования
            
        Returns:
            List: Результаты тестирования
        """
        if not self.client:
            logger.error("API ключ OpenAI не установлен. Невозможно выполнить тест с API.")
            return []
        
        if not self.examples:
            logger.warning("Нет загруженных данных для тестирования")
            return []
        
        # Ограничиваем количество примеров
        test_examples = self.examples[:min(num_examples, len(self.examples))]
        results = []
        
        for i, example in enumerate(test_examples):
            messages = example.get('messages', [])
            
            # Используем для запроса только системное и пользовательское сообщения
            input_messages = [
                msg for msg in messages 
                if msg.get('role') in ('system', 'user')
            ]
            
            # Находим ожидаемый ответ
            expected_response = None
            for msg in messages:
                if msg.get('role') == 'assistant':
                    expected_response = msg.get('content')
                    break
            
            if not input_messages:
                logger.warning(f"Пример {i} не содержит сообщений для запроса")
                continue
            
            try:
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=input_messages,
                    temperature=0.7
                )
                
                actual_response = response.choices[0].message.content
                
                result = {
                    "example_index": i,
                    "input_messages": input_messages,
                    "expected_response": expected_response,
                    "actual_response": actual_response,
                    "tokens_used": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
                
                # Добавляем информацию о совпадении ответов
                if expected_response == actual_response:
                    result["match"] = "exact"
                elif expected_response and actual_response and expected_response in actual_response:
                    result["match"] = "partial"
                else:
                    result["match"] = "none"
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Ошибка при тестировании примера {i}: {e}")
                results.append({
                    "example_index": i,
                    "input_messages": input_messages,
                    "error": str(e)
                })
        
        return results
    
    def print_stats(self, stats: Dict[str, Any]):
        """
        Выводит статистику набора данных в консоль.
        
        Args:
            stats: Словарь со статистикой
        """
        print("\n" + "=" * 60)
        print("АНАЛИЗ НАБОРА ДАННЫХ")
        print("=" * 60)
        
        print(f"\nФайл: {self.file_path}")
        print(f"Всего примеров: {stats['total_examples']}")
        print(f"Уникальных системных промптов: {stats['unique_system_prompts']}")
        print(f"Уникальных пользовательских запросов: {stats['unique_user_prompts']}")
        print(f"Уникальных ответов ассистента: {stats['unique_assistant_prompts']}")
        
        if "diversity_warning" in stats:
            print(f"\n⚠️ {stats['diversity_warning']}")
        
        # Вывод информации о структуре примеров
        print("\nСтруктуры примеров:")
        for structure, count in stats.get('examples_by_structure', {}).items():
            print(f"- {structure}: {count} примеров")
        
        # Вывод информации об ошибках форматирования
        if stats.get('format_errors'):
            print("\nОшибки форматирования:")
            for error in stats['format_errors'][:5]:  # Ограничиваем вывод первыми 5 ошибками
                print(f"- Пример {error['example_index']}: {error['error']}")
            
            if len(stats['format_errors']) > 5:
                print(f"  ... и еще {len(stats['format_errors']) - 5} ошибок")
        else:
            print("\n✅ Ошибок форматирования не обнаружено")
        
        # Вывод информации о дубликатах
        duplicates = stats.get('duplicates', {})
        duplicate_users = duplicates.get('user_prompts', {})
        duplicate_assistants = duplicates.get('assistant_responses', {})
        
        if duplicate_users:
            print(f"\nОбнаружено {len(duplicate_users)} дубликатов пользовательских запросов")
        else:
            print("\n✅ Дубликатов пользовательских запросов не обнаружено")
            
        if duplicate_assistants:
            print(f"Обнаружено {len(duplicate_assistants)} дубликатов ответов ассистента")
            # Вывод примера дубликата
            for response, indices in list(duplicate_assistants.items())[:1]:
                print(f"\nПример ответа, повторяющегося {len(indices)} раз:")
                print(f"- {response[:200]}..." if len(response) > 200 else f"- {response}")
                print(f"  Встречается в примерах: {indices[:5]}...")
        else:
            print("✅ Дубликатов ответов ассистента не обнаружено")
        
        print("\n" + "=" * 60)

def main():
    """Основная функция скрипта."""
    parser = argparse.ArgumentParser(description="Анализатор наборов данных JSONL для OpenAI")
    parser.add_argument("file_path", help="Путь к JSONL файлу с данными")
    parser.add_argument("--test-api", action="store_true", help="Тестировать примеры с использованием OpenAI API")
    parser.add_argument("--test-count", type=int, default=1, help="Количество примеров для тестирования с API")
    parser.add_argument("--output", help="Путь для сохранения результатов анализа в JSON")
    args = parser.parse_args()
    
    # Убедимся, что директория для логов существует
    os.makedirs('logs', exist_ok=True)
    
    # Проверяем существование файла
    if not os.path.exists(args.file_path):
        print(f"❌ Ошибка: Файл {args.file_path} не найден")
        return 1
    
    analyzer = JSONLDatasetAnalyzer(args.file_path)
    if not analyzer.load_data():
        print("❌ Ошибка при загрузке данных. См. логи для подробностей.")
        return 1
    
    # Анализируем набор данных
    stats = analyzer.analyze_dataset()
    analyzer.print_stats(stats)
    
    # Если запрошено тестирование с API, выполняем его
    if args.test_api:
        if not OPENAI_API_KEY:
            print("\n❌ OPENAI_API_KEY не установлен. Невозможно выполнить тест с API.")
            return 1
        
        print("\nТестирование примеров с использованием OpenAI API...")
        results = analyzer.test_with_api(num_examples=args.test_count)
        
        for i, result in enumerate(results):
            print(f"\nПример {result.get('example_index')}:")
            
            if "error" in result:
                print(f"❌ Ошибка: {result['error']}")
                continue
            
            match_status = result.get('match', 'unknown')
            if match_status == 'exact':
                print("✅ Точное совпадение ответа")
            elif match_status == 'partial':
                print("⚠️ Частичное совпадение ответа")
            else:
                print("❌ Ответы не совпадают")
            
            # Вывод информации о токенах
            tokens = result.get('tokens_used', {})
            if tokens:
                print(f"Использовано токенов: {tokens.get('total_tokens', 0)} "
                      f"(запрос: {tokens.get('prompt_tokens', 0)}, "
                      f"ответ: {tokens.get('completion_tokens', 0)})")
    
    # Сохраняем результаты в файл, если указан путь
    if args.output:
        try:
            output_data = {
                "file_path": args.file_path,
                "analysis": stats,
            }
            
            # Добавляем результаты тестирования API, если они есть
            if args.test_api and 'results' in locals():
                output_data["api_test_results"] = results
            
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"\nРезультаты анализа сохранены в {args.output}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении результатов: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
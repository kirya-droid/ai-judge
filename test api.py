import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

print("🔍 Тестируем DeepSeek API напрямую")
print(f"Ключ: {DEEPSEEK_API_KEY[:5]}...{DEEPSEEK_API_KEY[-5:]}")
print("-" * 50)

# Вариант 1: без /v1
url1 = "https://api.deepseek.com/chat/completions"
# Вариант 2: с /v1
url2 = "https://api.deepseek.com/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
}

data = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко."},
        {"role": "user", "content": "Скажи 'Привет' одним словом"}
    ],
    "stream": False,
    "max_tokens": 10
}

print("📡 Вариант 1 (без /v1):")
try:
    response = requests.post(url1, headers=headers, json=data, timeout=10)
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text[:200]}")
except Exception as e:
    print(f"Ошибка: {e}")

print("\n" + "-" * 50)

print("📡 Вариант 2 (с /v1):")
try:
    response = requests.post(url2, headers=headers, json=data, timeout=10)
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text[:200]}")
except Exception as e:
    print(f"Ошибка: {e}")
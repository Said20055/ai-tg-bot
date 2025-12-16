import os
import base64
import aiohttp
import logging
from openai import AsyncOpenAI

# Получи ключ: https://openrouter.ai/keys
SYSTEM_PROMPT = """
Ты — продвинутый и полезный AI-ассистент в Telegram боте.
Твои основные инструкции:
1. Язык: Всегда отвечай на русском языке (если пользователь не попросил иное).
2. Форматирование: Активно используй Markdown для улучшения читаемости:
   - Выделяй ключевые слова **жирным**.
   - Используй списки для перечислений.
   - Оборачивай код в тройные кавычки (```language ... ```).
3. Стиль: Будь вежливым, дружелюбным, но говори по делу. Избегай лишней воды.
4. Контекст: Помни, что сообщения читают с телефона, поэтому старайся не писать огромные полотна текста без разделения на абзацы.
5. Если вопрос касается программирования, давай рабочий и объясненный код.
"""

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-...") 
SITE_URL = "https://your-site-url.com" # Требование OpenRouter (можно любое)
APP_NAME = "My Telegram Bot"

# Настройка клиента
client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# Модели
TEXT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct" # Или "openai/gpt-4o-mini"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

async def generate_text(user_prompt: str) -> str:
    """Генерация текста через OpenRouter с системным промтом"""
    try:
        completion = await client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": SITE_URL,
                "X-Title": APP_NAME,
            },
            model=TEXT_MODEL,
            messages=[
                # 1. Сначала даем инструкцию "кто ты"
                {"role": "system", "content": SYSTEM_PROMPT},
                # 2. Затем передаем запрос пользователя
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7, # 0.7 - баланс между креативностью и точностью
        )
        logging.info(f"OpenRouter Response: {completion}")
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Text Error: {e}")
        return "Произошла ошибка при генерации текста. Попробуйте позже."

async def analyze_image(prompt: str, image_bytes: bytes) -> str:
    """Анализ изображения (Vision)"""
    try:
        # Кодируем байты в base64 строку
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        completion = await client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": SITE_URL,
                "X-Title": APP_NAME,
            },
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Vision Error: {e}")
        return "Не удалось распознать изображение."

async def generate_image_flux(prompt: str) -> bytes:
    """
    Генерация картинки Flux. 
    Используем Pollinations.ai (бесплатно и качественно), 
    так как через OpenRouter генерация картинок сложнее в настройке.
    """
    try:
        # Кодируем промпт для URL
        encoded_prompt = prompt.replace(" ", "%20")
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=1024&nologo=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read() # Возвращаем байты картинки
                else:
                    print(f"Flux Error: Status {resp.status}")
                    return None
    except Exception as e:
        print(f"Flux Generate Error: {e}")
        return None
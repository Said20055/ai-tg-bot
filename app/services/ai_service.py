import os
import asyncio
import aiohttp
from google import genai
from PIL import Image

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_GOOGLE = "gemini-2.0-flash"

client = None
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)

# --- ЗАГОТОВЛЕННЫЙ ПРОМТ ---
SYSTEM_INSTRUCTION = (
    "Ты — полезный ассистент в Telegram. Отвечай на русском языке.\n"
    "ВАЖНЫЕ ПРАВИЛА:\n"
    "1. ФОРМАТИРОВАНИЕ: Используй ТОЛЬКО HTML теги. "
    "Поддерживаемые теги: <b>жирный</b>, <i>курсив</i>, <code>код</code>, "
    "<pre>блок кода</pre>, <a href='...'>ссылка</a>. "
    "⛔️ ЗАПРЕЩЕНО использовать Markdown (символы **, __, ```), так как это вызовет ошибку.\n"
    "2. ДЛИНА: Твой ответ СТРОГО не должен превышать 3800 символов. "
    "Если ответ требует больше места — сократи его, выдели главное или разбей на пункты."
)

async def generate_text(user_prompt: str):
    if not client: return "Ошибка: Нет ключа Google"
    try:
        # Соединяем системный промт с запросом пользователя
        full_prompt = f"{SYSTEM_INSTRUCTION}\n\nЗапрос пользователя: {user_prompt}"

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_GOOGLE,
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"Ошибка AI: {str(e)}"

async def analyze_image(user_prompt: str, image_bytes):
    if not client: return "Ошибка: Нет ключа Google"
    try:
        pil_image = Image.open(image_bytes)
        
        # Для картинок тоже добавляем инструкцию
        full_prompt = [SYSTEM_INSTRUCTION, f"Запрос: {user_prompt}", pil_image]
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_GOOGLE,
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"Ошибка Vision: {str(e)}"

async def generate_image_flux(prompt: str):
    import random
    seed = random.randint(1, 100000)
    # Flux работает лучше с английским промтом, но пока оставим как есть
    url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&model=flux&seed={seed}&nologo=true"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
            return None
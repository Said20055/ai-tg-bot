import io
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile

# Проверь правильность путей к твоим файлам!
# Если файлы лежат рядом, убери две точки: from database import ...
from ..database.orm import get_user, increment_usage
from ..services.ai_service import generate_text, generate_image_flux, analyze_image
from datetime import datetime

router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def send_chunked_response(message: types.Message, text: str):
    """Безопасная отправка длинных сообщений"""
    if not text:
        await message.answer("Пустой ответ от нейросети.")
        return

    MAX_LENGTH = 4000 
    
    # Пытаемся отправить как Markdown, если не выйдет - как текст
    # OpenRouter часто возвращает Markdown разметку (**bold**, `code`)
    parse_mode = ParseMode.MARKDOWN
    
    try:
        if len(text) <= MAX_LENGTH:
            await message.answer(text, parse_mode=parse_mode)
        else:
            for x in range(0, len(text), MAX_LENGTH):
                chunk = text[x : x + MAX_LENGTH]
                await message.answer(chunk, parse_mode=parse_mode)
    except Exception:
        # Если разметка сломалась, отправляем без форматирования
        if len(text) <= MAX_LENGTH:
            await message.answer(text)
        else:
            for x in range(0, len(text), MAX_LENGTH):
                chunk = text[x : x + MAX_LENGTH]
                await message.answer(chunk)


# --- ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    # Регистрируем или получаем юзера
    user = await get_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    
    is_premium = False
    if user.premium_until and user.premium_until > datetime.utcnow():
        is_premium = True
        
    if is_premium:
        status = f"🌟 Premium (до {user.premium_until.strftime('%d.%m.%Y')})"
        text_limit = "Безлимит"
        img_limit = "Безлимит"
    else:
        status = "👤 Free"
        # Если у тебя есть файл middlewares.py с лимитами, импортируй оттуда
        # Иначе поставь значения вручную
        text_limit = "10" 
        img_limit = "5"
        
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Твой статус: **{status}**\n\n"
        f"📊 **Твоя статистика:**\n"
        f"📝 Текст: `{user.text_usage}` / {text_limit}\n"
        f"🎨 Картинки: `{user.image_usage}` / {img_limit}\n\n"
        "Купить подписку: /buy\n"
        "Напиши запрос или отправь фото!",
        parse_mode=ParseMode.MARKDOWN
    )

@router.message(Command("img"))
async def img_handler(message: types.Message):
    """Генерация картинок (Flux)"""
    prompt = message.text.replace("/img", "").strip()
    if not prompt: 
        return await message.answer("Пример: `/img кот в космосе`")
    
    msg = await message.answer("🎨 Рисую (Flux)...")
    
    # Вызываем сервис генерации
    img_data = await generate_image_flux(prompt)
    
    if img_data:
        await increment_usage(message.from_user.id, 'image')
        file = BufferedInputFile(img_data, filename="image.jpg")
        await message.answer_photo(file, caption=f"🎨 {prompt}")
        await msg.delete()
    else:
        await msg.edit_text("Ошибка генерации или сервис недоступен.")

@router.message(F.photo)
async def vision_handler(message: types.Message, bot: Bot):
    """Обработка фото (Vision)"""
    msg = await message.answer("👀 Смотрю...")
    
    # 1. Скачиваем фото правильно для aiogram 3.x
    photo = message.photo[-1] # Берем лучшее качество
    file_io = io.BytesIO()
    await bot.download(photo, destination=file_io)
    file_bytes = file_io.getvalue()
    
    # 2. Формируем промпт
    prompt = message.caption if message.caption else "Опиши подробно, что на фото."
    
    # 3. Отправляем в OpenRouter
    answer = await analyze_image(prompt, file_bytes)
    
    await increment_usage(message.from_user.id, 'text')
    await msg.delete()
    await send_chunked_response(message, answer)

@router.message(F.text)
async def text_handler(message: types.Message):
    """Обычный текстовый запрос"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    # Просто передаем текст, сервис сам сформирует messages
    answer = await generate_text(message.text)
    
    await increment_usage(message.from_user.id, 'text')
    await send_chunked_response(message, answer)
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from ..database.orm import get_user, increment_usage
from ..services.ai_service import generate_text, generate_image_flux, analyze_image
from datetime import datetime

router = Router()

# --- ФУНКЦИЯ БЕЗОПАСНОЙ ОТПРАВКИ (Нарезка) ---
async def send_chunked_response(message: types.Message, text: str):
    """
    Если текст длиннее 4096 символов, разбивает его на части.
    """
    if not text:
        await message.answer("Пустой ответ от нейросети.")
        return

    # Лимит Telegram 4096, берем 4000 с запасом
    MAX_LENGTH = 4000 

    if len(text) <= MAX_LENGTH:
        await message.answer(text, parse_mode=ParseMode.HTML)
    else:
        # Разбиваем текст на куски
        for x in range(0, len(text), MAX_LENGTH):
            chunk = text[x : x + MAX_LENGTH]
            # Отправляем кусок
            await message.answer(chunk, parse_mode=ParseMode.HTML)


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    
    is_premium = False
    if user.premium_until and user.premium_until > datetime.utcnow():
        is_premium = True
        
    if is_premium:
        status = f"🌟 Premium (до {user.premium_until.strftime('%d.%m.%Y')})"
        text_limit = "Безлимит"
        img_limit = "Безлимит"
    else:
        status = "👤 Free"
        from middlewares import FREE_TEXT_LIMIT, FREE_IMAGE_LIMIT
        text_limit = f"{FREE_TEXT_LIMIT}"
        img_limit = f"{FREE_IMAGE_LIMIT}"
        
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Твой статус: **{status}**\n\n"
        f"📊 **Твоя статистика:**\n"
        f"📝 Текст: `{user.text_usage}` / {text_limit}\n"
        f"🎨 Картинки: `{user.image_usage}` / {img_limit}\n\n"
        "Купить подписку: /buy",
        parse_mode=ParseMode.MARKDOWN # Тут Markdown безопасен, т.к. текст наш
    )

@router.message(Command("img"))
async def img_handler(message: types.Message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt: return await message.answer("Пример: `/img кот`")
    
    msg = await message.answer("🎨 Рисую...")
    img_data = await generate_image_flux(prompt)
    
    if img_data:
        await increment_usage(message.from_user.id, 'image')
        from aiogram.types import BufferedInputFile
        file = BufferedInputFile(img_data, filename="image.jpg")
        await message.answer_photo(file, caption=f"🎨 {prompt}")
        await msg.delete()
    else:
        await msg.edit_text("Ошибка генерации.")

@router.message(F.photo)
async def vision_handler(message: types.Message):
    msg = await message.answer("👀 Смотрю...")
    
    # Скачиваем фото
    file = await message.bot.get_file(message.photo[-1].file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    
    # Спрашиваем нейросеть (если есть подпись к фото - используем её, иначе дефолт)
    prompt = message.caption if message.caption else "Опиши подробно, что на фото."
    
    answer = await analyze_image(prompt, file_bytes)
    
    await increment_usage(message.from_user.id, 'text')
    await msg.delete()
    # Используем безопасную отправку
    await send_chunked_response(message, answer)

@router.message(F.text)
async def text_handler(message: types.Message):
    # Отправляем "печатает...", чтобы юзер видел активность
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    answer = await generate_text(message.text)
    
    await increment_usage(message.from_user.id, 'text')
    
    # Используем безопасную отправку
    await send_chunked_response(message, answer)
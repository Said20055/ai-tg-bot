from aiogram import BaseMiddleware
from aiogram.types import Message
from app.database.orm import get_user
from datetime import datetime

FREE_TEXT_LIMIT = 100
FREE_IMAGE_LIMIT = 5

class LimitsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Если это не сообщение (например, нажатие кнопки), пропускаем
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        # Получаем пользователя (или создаем, если нет)
        user = await get_user(user_id, event.from_user.username, event.from_user.full_name)

        # 1. Проверка на ПРЕМИУМ
        is_premium = False
        if user.premium_until and user.premium_until > datetime.utcnow():
            is_premium = True

        if is_premium:
            return await handler(event, data)

        # 2. ЛОГИКА ЛИМИТОВ
        
        # Получаем текст сообщения безопасно
        msg_text = event.text or event.caption or ""
        
        # А) Проверка на генерацию картинки (/img)
        # Проверяем именно event.text, т.к. команды работают только в тексте
        if event.text and event.text.startswith('/img'):
            if user.image_usage >= FREE_IMAGE_LIMIT:
                await event.answer("⛔️ Лимит картинок исчерпан!\nКупите подписку: /buy")
                return

        # Б) Проверка обычного текста ИЛИ фото (Vision)
        # Мы считаем запрос платным (тратящим лимит), если:
        # 1. Это ФОТО (Vision запрос)
        # 2. ИЛИ Это ТЕКСТ, который НЕ является командой (не начинается с /)
        
        is_photo = bool(event.photo)
        is_text_request = event.text and not event.text.startswith('/')

        if is_photo or is_text_request:
            if user.text_usage >= FREE_TEXT_LIMIT:
                await event.answer("⛔️ Лимит запросов исчерпан!\nКупите подписку: /buy")
                return

        return await handler(event, data)
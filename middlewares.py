from aiogram import BaseMiddleware
from aiogram.types import Message
from app.database.orm import get_user
from datetime import datetime

FREE_TEXT_LIMIT = 100
FREE_IMAGE_LIMIT = 1

class LimitsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        user = await get_user(user_id, event.from_user.username, event.from_user.full_name)

        # Проверка на премиум по времени
        is_premium = False
        if user.premium_until and user.premium_until > datetime.utcnow():
            is_premium = True

        # Если премиум - пропускаем всё
        if is_premium:
            return await handler(event, data)

        # Логика лимитов для бесплатных
        is_img = event.text and event.text.startswith('/img')
        
        if is_img:
            if user.image_usage >= FREE_IMAGE_LIMIT:
                await event.answer("⛔️ Лимит картинок исчерпан!\nКупите подписку: /buy")
                return
        elif not event.text.startswith('/'):
            if user.text_usage >= FREE_TEXT_LIMIT:
                await event.answer("⛔️ Лимит текста исчерпан!\nКупите подписку: /buy")
                return

        return await handler(event, data)
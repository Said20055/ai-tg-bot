import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Импорты
from app.database.orm import init_db
from middlewares import LimitsMiddleware
from app.handlers import user, payment, admin
from app.handlers.webhook_handler import yookassa_webhook

load_dotenv()

# Настройки веб-сервера (слушаем порт 8000 внутри Докера)
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8000
# Путь, на который будет стучаться ЮKassa
WEBHOOK_PATH = "/webhook/yookassa"

async def on_startup(app):
    """Эта функция запустится при старте сервера"""
    # 1. Инициализируем БД
    await init_db()
    
    # 2. Запускаем бота (Polling) в фоновом режиме
    # Мы используем polling для бота, но сервер для платежей. Это удобно.
    asyncio.create_task(run_bot_polling(app["bot"], app["dp"]))

async def run_bot_polling(bot, dp):
    """Запуск бота"""
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

def main():
    logging.basicConfig(level=logging.INFO)

    TG_TOKEN = os.getenv("TG_TOKEN")
    if not TG_TOKEN:
        exit("Error: TG_TOKEN not found")

    # Инициализация бота
    bot = Bot(token=TG_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    # Подключаем Middleware и Роутеры
    dp.include_router(admin.router)
    dp.message.middleware(LimitsMiddleware())
    dp.include_router(payment.router)
    dp.include_router(user.router)
    

    # --- НАСТРОЙКА ВЕБ-СЕРВЕРА ---
    app = web.Application()
    
    # Сохраняем бота и диспетчер внутри приложения, чтобы иметь к ним доступ в вебхуке
    app["bot"] = bot
    app["dp"] = dp

    # Регистрируем адрес для ЮКассы
    app.router.add_post(WEBHOOK_PATH, yookassa_webhook)
    
    # Говорим серверу, что делать при старте
    app.on_startup.append(on_startup)

    # Запускаем сервер
    print(f"🚀 Сервер запущен на порту {WEB_SERVER_PORT}")
    print(f"🔗 Ожидаем вебхуки на {WEBHOOK_PATH}")
    
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
import logging
from aiohttp import web
from aiogram import Bot
from yookassa.domain.notification import WebhookNotificationFactory

# Импортируем функцию выдачи премиума из базы
from ..database.orm import add_premium_time

async def yookassa_webhook(request: web.Request):
    """
    Обработчик запросов от ЮKassa.
    """
    # 1. Читаем данные запроса
    try:
        event_json = await request.json()
    except Exception:
        # Если пришел мусор, просто игнорируем
        return web.Response(status=400)

    # 2. Парсим уведомление через SDK ЮКассы
    try:
        notification_object = WebhookNotificationFactory().create(event_json)
        response_object = notification_object.object
        
        # Нас интересует только успешная оплата
        if notification_object.event == "payment.succeeded":
            
            # Достаем данные, которые мы зашили в metadata на Этапе 2
            user_id = int(response_object.metadata.get("user_id"))
            duration = int(response_object.metadata.get("duration"))
            amount = response_object.amount.value

            logging.info(f"💰 Платеж успешен: User {user_id}, Сумма {amount}, Дней {duration}")

            # 3. Выдаем подписку в БД
            new_date = await add_premium_time(user_id, duration)
            
            # 4. Уведомляем пользователя через бота
            # Достаем бота из "контекста" приложения
            bot: Bot = request.app["bot"]
            
            try:
                date_str = new_date.strftime("%d.%m.%Y")
                await bot.send_message(
                    user_id,
                    f"✅ **Оплата прошла успешно!**\n\n"
                    f"Ваша Premium подписка активна до: `{date_str}`\n"
                    "Все лимиты сняты. Приятного использования!"
                )
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение юзеру: {e}")

        # Отвечаем ЮКассе "ОК", чтобы она перестала слать уведомления
        return web.Response(status=200)

    except Exception as e:
        logging.error(f"Ошибка обработки вебхука: {e}")
        return web.Response(status=500)
import uuid
import os
import logging
from yookassa import Configuration, Payment

# Настраиваем ЮKassa
# Ключи берутся из .env, который мы настроили ранее
Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

def create_payment(amount: float, description: str, user_id: int, tariff_id: int, duration: int):
    """
    Создает платеж в ЮKassa.
    Возвращает: (payment_url, payment_id)
    """
    try:
        idempotence_key = str(uuid.uuid4())
        
        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/ТВОЙ_БОТ" # Замени на юзернейм своего бота
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id,
                "tariff_id": tariff_id, # Важно: сохраняем ID тарифа
                "duration": duration
            }
        }, idempotence_key)

        return payment.confirmation.confirmation_url, payment.id
        
    except Exception as e:
        logging.error(f"Ошибка создания платежа ЮKassa: {e}")
        return None, None
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ..database.orm import get_active_tariffs, get_tariff_by_id
from ..services.payment import create_payment

router = Router()

# --- 1. КОМАНДА /buy ---
@router.message(Command("buy"))
async def cmd_buy(message: types.Message):
    # Получаем тарифы из базы данных
    tariffs = await get_active_tariffs()
    
    if not tariffs:
        await message.answer("😔 К сожалению, сейчас нет доступных тарифов.")
        return

    # Строим клавиатуру
    builder = InlineKeyboardBuilder()
    
    for tariff in tariffs:
        # Текст кнопки: "1 Месяц - 299₽"
        btn_text = f"{tariff.name} — {tariff.price}₽"
        # В callback_data кладем ID тарифа: "buy_1", "buy_2"
        builder.button(text=btn_text, callback_data=f"buy_{tariff.id}")
    
    builder.adjust(1) # Кнопки в один столбик
    
    await message.answer(
        "💎 **Выберите тариф Premium:**\n\n"
        "Вы получите безлимитный доступ к генерации текста и картинок (Flux).\n"
        "Выберите подходящий вариант:",
        reply_markup=builder.as_markup()
    )

# --- 2. ОБРАБОТКА ВЫБОРА ТАРИФА ---
@router.callback_query(F.data.startswith("buy_"))
async def process_buy_callback(call: types.CallbackQuery):
    # Парсим ID тарифа из нажатой кнопки
    tariff_id = int(call.data.split("_")[1])
    
    # Ищем тариф в базе, чтобы узнать актуальную цену
    tariff = await get_tariff_by_id(tariff_id)
    
    if not tariff:
        await call.answer("Тариф не найден или удален", show_alert=True)
        return

    # Создаем ссылку на оплату через наш сервис
    payment_url, payment_id = create_payment(
        amount=tariff.price,
        description=f"Подписка: {tariff.name}",
        user_id=call.from_user.id,
        tariff_id=tariff.id,
        duration=tariff.duration_days
    )

    if not payment_url:
        await call.answer("Ошибка платежной системы", show_alert=True)
        return

    # Кнопка для оплаты
    builder = InlineKeyboardBuilder()
    builder.button(text=f"💳 Оплатить {tariff.price}₽", url=payment_url)
    builder.button(text="🔙 Назад", callback_data="return_buy") # Можно реализовать отмену

    await call.message.edit_text(
        f"📄 Счет на оплату сформирован.\n\n"
        f"Тариф: **{tariff.name}**\n"
        f"Срок: **{tariff.duration_days} дней**\n"
        f"Сумма: **{tariff.price} RUB**\n\n"
        "Нажмите кнопку ниже для оплаты картой или через SBP.",
        reply_markup=builder.as_markup()
    )
    await call.answer()
    
    
    
    @router.callback_query(F.data =="return_buy")
    async def return_buy(call: types.CallbackQuery):
        await call.message.delete()
        await cmd_buy(call.message)
        await call.answer()
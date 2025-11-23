import os
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..database.orm import get_stats, add_premium_time, remove_premium, get_all_users_ids

# --- ЧИТАЕМ СПИСОК АДМИНОВ ---
# Разбиваем строку "id1,id2" на список чисел
admin_ids_str = os.getenv("ADMIN_IDS", "")
print(f"🔍 DEBUG: Строка из .env: '{admin_ids_str}'")
ADMIN_IDS = [int(x) for x in admin_ids_str.split(",") if x.strip()]

router = Router()

# --- СОСТОЯНИЯ (FSM) ---
class AdminState(StatesGroup):
    waiting_for_user_id = State()      # Выдача: ждем ID
    waiting_for_duration = State()     # Выдача: ждем срок
    waiting_for_del_id = State()       # Удаление: ждем ID
    waiting_for_broadcast = State()    # Рассылка: ждем текст
    confirm_broadcast = State()        # Рассылка: ждем подтверждения

# --- ФИЛЬТР АДМИНА ---
def is_admin(message: types.Message):
    return message.from_user.id in ADMIN_IDS

# --- 1. ГЛАВНОЕ МЕНЮ ---
@router.message(Command("admin"))
async def admin_menu(message: types.Message):
    if not is_admin(message): return

    stats = await get_stats()

    text = (
        f"👑 **Админ Панель**\n"
        f"Вы вошли как: `{message.from_user.id}`\n\n"
        f"👥 Пользователей: `{stats['total_users']}`\n"
        f"🌟 Активных подписок: `{stats['active_premium']}`\n"
        f"📝 Текст. запросов: `{stats['total_text']}`\n"
        f"🎨 Картинок: `{stats['total_images']}`"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Выдать Премиум", callback_data="admin_give_prem")
    builder.button(text="💀 Забрать Премиум", callback_data="admin_del_prem")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🔄 Обновить", callback_data="admin_refresh")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "admin_refresh")
async def refresh_stats(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    stats = await get_stats()
    text = (
        f"👑 **Админ Панель**\n"
        f"Вы вошли как: `{call.from_user.id}`\n\n"
        f"👥 Пользователей: `{stats['total_users']}`\n"
        f"🌟 Активных подписок: `{stats['active_premium']}`\n"
        f"📝 Текст. запросов: `{stats['total_text']}`\n"
        f"🎨 Картинок: `{stats['total_images']}`"
    )
    try:
        await call.message.edit_text(text, reply_markup=call.message.reply_markup)
        await call.answer("Обновлено")
    except:
        await call.answer("Нет изменений")

# --- 2. ВЫДАЧА ПРЕМИУМА ---
@router.callback_query(F.data == "admin_give_prem")
async def start_give_prem(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("✍️ Введите **Telegram ID** пользователя:")
    await state.set_state(AdminState.waiting_for_user_id)
    await call.answer()

@router.message(AdminState.waiting_for_user_id)
async def process_give_id(message: types.Message, state: FSMContext):
    try:
        uid = int(message.text)
        await state.update_data(target_id=uid)
        await message.answer("📅 Срок (дней):")
        await state.set_state(AdminState.waiting_for_duration)
    except:
        await message.answer("❌ Введите число.")

@router.message(AdminState.waiting_for_duration)
async def process_give_days(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        data = await state.get_data()
        target_id = data['target_id']
        
        new_date = await add_premium_time(target_id, days)
        await message.answer(f"✅ Премиум для `{target_id}` выдан до `{new_date.strftime('%d.%m.%Y')}`")
        await state.clear()
        
        # Уведомление юзеру
        try: await message.bot.send_message(target_id, f"🎁 Вам выдан Premium на {days} дней!")
        except: pass
    except:
        await message.answer("❌ Введите число.")

# --- 3. УДАЛЕНИЕ ПРЕМИУМА (НОВОЕ) ---
@router.callback_query(F.data == "admin_del_prem")
async def start_del_prem(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("💀 Введите **Telegram ID** у кого забрать подписку:")
    await state.set_state(AdminState.waiting_for_del_id)
    await call.answer()

@router.message(AdminState.waiting_for_del_id)
async def process_del_id(message: types.Message, state: FSMContext):
    try:
        uid = int(message.text)
        await remove_premium(uid)
        await message.answer(f"✅ Подписка пользователя `{uid}` аннулирована.")
        await state.clear()
    except:
        await message.answer("❌ Введите число.")

# --- 4. РАССЫЛКА С ПОДТВЕРЖДЕНИЕМ (НОВОЕ) ---
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📢 Пришлите сообщение (текст/фото/видео), которое нужно разослать:")
    await state.set_state(AdminState.waiting_for_broadcast)
    await call.answer()

@router.message(AdminState.waiting_for_broadcast)
async def prepare_broadcast(message: types.Message, state: FSMContext):
    # Сохраняем ID сообщения и ID чата, чтобы потом скопировать
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    
    # Кнопки подтверждения
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="confirm_send")
    builder.button(text="❌ Отмена", callback_data="cancel_send")
    builder.adjust(2)
    
    await message.answer("👀 **Превью рассылки.**\nВот так будет выглядеть сообщение. Отправляем?", reply_markup=builder.as_markup())
    # Копируем сообщение админу, чтобы он проверил
    await message.copy_to(message.chat.id)
    
    await state.set_state(AdminState.confirm_broadcast)

@router.callback_query(AdminState.confirm_broadcast, F.data == "confirm_send")
async def execute_broadcast(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    msg_id = data['msg_id']
    from_chat_id = data['chat_id']
    
    users = await get_all_users_ids()
    await call.message.edit_text(f"🚀 Рассылка началась на {len(users)} пользователей...")
    
    count = 0
    for uid in users:
        try:
            await call.bot.copy_message(chat_id=uid, from_chat_id=from_chat_id, message_id=msg_id)
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass
            
    await call.message.answer(f"🏁 Рассылка завершена. Доставлено: {count}")
    await state.clear()

@router.callback_query(AdminState.confirm_broadcast, F.data == "cancel_send")
async def cancel_broadcast(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ Рассылка отменена.")
    await state.clear()
import os
from datetime import datetime, timedelta
from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, select, update, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

# --- КОНФИГУРАЦИЯ ---
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "changeme")
DB_NAME = os.getenv("DB_NAME", "ai_bot_db")
DB_HOST = os.getenv("DB_HOST", "db")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

# --- МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    
    text_usage: Mapped[int] = mapped_column(Integer, default=0)
    image_usage: Mapped[int] = mapped_column(Integer, default=0)
    
    premium_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# --- НОВАЯ МОДЕЛЬ: ТАРИФЫ ---
class Tariff(Base):
    __tablename__ = 'tariffs'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)        # Название: "1 Месяц"
    description: Mapped[str] = mapped_column(String, nullable=True)  # Описание
    price: Mapped[int] = mapped_column(Integer, nullable=False)      # Цена в рублях
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False) # Срок действия
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)   # Активен ли тариф?

# --- ФУНКЦИИ ИНИЦИАЛИЗАЦИИ ---

async def init_db():
    """Создает таблицы и базовые тарифы, если их нет"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем базовые тарифы, если таблица пустая
    await create_initial_tariffs()

async def create_initial_tariffs():
    async with async_session() as session:
        # Проверяем, есть ли хоть один тариф
        result = await session.execute(select(Tariff))
        if result.first():
            return # Тарифы уже есть, ничего не делаем

        # Если пусто - добавляем стандартные
        tariffs = [
            Tariff(name="1 Месяц", price=299, duration_days=30, description="Стандартный план"),
            Tariff(name="3 Месяца", price=799, duration_days=90, description="Выгодный план (-10%)"),
            Tariff(name="1 Год", price=2490, duration_days=365, description="Максимальная выгода")
        ]
        session.add_all(tariffs)
        await session.commit()
        print("✅ Базовые тарифы созданы в БД")

# --- ФУНКЦИИ ДЛЯ ЮЗЕРА ---

async def get_user(tg_id: int, username: str = None, full_name: str = None):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=tg_id, username=username, full_name=full_name)
            session.add(user)
            await session.commit()
            return user
        return user

async def add_premium_time(tg_id: int, days: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        
        now = datetime.utcnow()
        if user.premium_until and user.premium_until > now:
            new_date = user.premium_until + timedelta(days=days)
        else:
            new_date = now + timedelta(days=days)
            
        await session.execute(
            update(User).where(User.telegram_id == tg_id).values(premium_until=new_date)
        )
        await session.commit()
        return new_date

async def increment_usage(tg_id: int, type: str):
    async with async_session() as session:
        field = User.text_usage if type == 'text' else User.image_usage
        await session.execute(
            update(User).where(User.telegram_id == tg_id).values({field: field + 1})
        )
        await session.commit()

# --- ФУНКЦИИ ДЛЯ ТАРИФОВ ---

async def get_active_tariffs():
    """Возвращает список активных тарифов для меню"""
    async with async_session() as session:
        query = select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price)
        result = await session.execute(query)
        return result.scalars().all()

async def get_tariff_by_id(tariff_id: int):
    """Ищет тариф по ID"""
    async with async_session() as session:
        return await session.get(Tariff, tariff_id)

async def get_all_users_ids():
    """Возвращает список telegram_id всех пользователей (для рассылки)"""
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        return result.scalars().all()

async def remove_premium(tg_id: int):
    """Аннулирует подписку пользователя"""
    async with async_session() as session:
        # Ставим дату в прошедшем времени
        past_date = datetime.utcnow() - timedelta(days=1)
        await session.execute(
            update(User).where(User.telegram_id == tg_id).values(premium_until=past_date)
        )
        await session.commit()


# Не забудь проверить импорты наверху файла:
# from sqlalchemy import func, select
# from datetime import datetime

async def get_stats():
    """
    Собирает полную статистику по боту.
    Возвращает словарь с данными.
    """
    async with async_session() as session:
        # 1. Общее количество пользователей
        total_users = await session.scalar(select(func.count(User.id)))

        # 2. Количество активных премиум-подписок
        # (где дата окончания больше, чем сейчас)
        active_premium = await session.scalar(
            select(func.count(User.id)).where(User.premium_until > datetime.utcnow())
        )

        # 3. Суммарное использование (сколько всего запросов обработал бот)
        total_text = await session.scalar(select(func.sum(User.text_usage)))
        total_images = await session.scalar(select(func.sum(User.image_usage)))

        # Если база пустая, SQL вернет None, заменяем на 0
        return {
            "total_users": total_users or 0,
            "active_premium": active_premium or 0,
            "total_text": total_text or 0,
            "total_images": total_images or 0
        }
import os
from datetime import datetime, timedelta
from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, select, update, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

# --- КОНФИГУРАЦИЯ ---
# SQLite хранит базу в одном файле. Здесь мы указываем имя файла "bot.db"
DATABASE_URL = "sqlite+aiosqlite:///bot.db"

# Создаем движок
# echo=False отключает вывод SQL-запросов в консоль (поставь True для отладки)
engine = create_async_engine(DATABASE_URL, echo=False)

# Создаем фабрику сессий
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

# --- МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    # BigInteger в SQLite работает корректно, хранит большие числа (ID телеграма)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    
    text_usage: Mapped[int] = mapped_column(Integer, default=0)
    image_usage: Mapped[int] = mapped_column(Integer, default=0)
    
    premium_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# --- МОДЕЛЬ ТАРИФОВ ---
class Tariff(Base):
    __tablename__ = 'tariffs'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

# --- ФУНКЦИИ ИНИЦИАЛИЗАЦИИ ---

async def init_db():
    """Создает таблицы и файл базы данных, если их нет"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем базовые тарифы
    await create_initial_tariffs()

async def create_initial_tariffs():
    async with async_session() as session:
        # Проверяем наличие тарифов
        result = await session.execute(select(Tariff))
        if result.first():
            return 

        tariffs = [
            Tariff(name="1 Месяц", price=299, duration_days=30, description="Стандартный план"),
            Tariff(name="3 Месяца", price=799, duration_days=90, description="Выгодный план (-10%)"),
            Tariff(name="1 Год", price=2490, duration_days=365, description="Максимальная выгода")
        ]
        session.add_all(tariffs)
        await session.commit()
        print("✅ Базовые тарифы созданы в SQLite (bot.db)")

# --- ФУНКЦИИ ДЛЯ ЮЗЕРА ---

async def get_user(tg_id: int, username: str = None, full_name: str = None):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=tg_id, username=username, full_name=full_name)
            session.add(user)
            await session.commit()
            # Обновляем объект, чтобы получить ID из базы
            await session.refresh(user) 
            return user
        return user

async def add_premium_time(tg_id: int, days: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return None # Или обработать ошибку, если юзера нет

        now = datetime.utcnow()
        if user.premium_until and user.premium_until > now:
            new_date = user.premium_until + timedelta(days=days)
        else:
            new_date = now + timedelta(days=days)
            
        # В SQLite обновление лучше делать через объект, но raw-update тоже работает
        user.premium_until = new_date
        session.add(user)
        await session.commit()
        return new_date

async def increment_usage(tg_id: int, type: str):
    async with async_session() as session:
        # Вариант с прямым SQL update работает быстрее
        field = User.text_usage if type == 'text' else User.image_usage
        await session.execute(
            update(User).where(User.telegram_id == tg_id).values({field: field + 1})
        )
        await session.commit()

# --- ФУНКЦИИ ДЛЯ ТАРИФОВ ---

async def get_active_tariffs():
    async with async_session() as session:
        query = select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price)
        result = await session.execute(query)
        return result.scalars().all()

async def get_tariff_by_id(tariff_id: int):
    async with async_session() as session:
        return await session.get(Tariff, tariff_id)

async def get_all_users_ids():
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        return result.scalars().all()

async def remove_premium(tg_id: int):
    async with async_session() as session:
        past_date = datetime.utcnow() - timedelta(days=1)
        await session.execute(
            update(User).where(User.telegram_id == tg_id).values(premium_until=past_date)
        )
        await session.commit()

async def get_stats():
    """
    Собирает полную статистику по боту.
    """
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))

        active_premium = await session.scalar(
            select(func.count(User.id)).where(User.premium_until > datetime.utcnow())
        )

        total_text = await session.scalar(select(func.sum(User.text_usage)))
        total_images = await session.scalar(select(func.sum(User.image_usage)))

        return {
            "total_users": total_users or 0,
            "active_premium": active_premium or 0,
            "total_text": total_text or 0,
            "total_images": total_images or 0
        }
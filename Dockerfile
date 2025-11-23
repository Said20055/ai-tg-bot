# Используем Python 3.11 Slim (Debian) — самый стабильный вариант для ML/AI ботов
FROM python:3.11-slim

# Переменные окружения для оптимизации Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /usr/src/app

# Устанавливаем системные зависимости
# gcc и libpq-dev нужны для сборки драйвера базы данных (asyncpg)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только requirements.txt (для кэширования слоев Docker)
COPY requirements.txt .

# Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта в контейнер
COPY . .


# Запускаем бота
CMD ["python", "main.py"]
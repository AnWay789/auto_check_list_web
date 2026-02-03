FROM python:3.13-slim

# Установка системных зависимостей + Node.js, Chromium для Lighthouse
RUN apt-get update && apt-get install -y \
    gcc \
    netcat-openbsd \
    postgresql-client \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get install -y \
    chromium \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
    && npm install -g lighthouse \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install --no-cache-dir poetry

# Настройка Poetry (не создавать виртуальное окружение, так как мы в контейнере)
RUN poetry config virtualenvs.create false

# Установка рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY pyproject.toml poetry.lock* ./
COPY README.md ./

# Установка зависимостей
RUN poetry install --no-interaction --no-ansi --no-root

# Копирование кода приложения
COPY . .

# Копирование entrypoint скрипта (миграции + создание суперпользователя при старте)
# Суперпользователь создаётся, если заданы DJANGO_SUPERUSER_USERNAME и DJANGO_SUPERUSER_PASSWORD
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Создание директории для статики
RUN mkdir -p /app/static

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings
# Путь к Chromium для Lighthouse (headless в контейнере)
ENV CHROME_PATH=/usr/bin/chromium

# Порт для Django
EXPOSE 8000

# Entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Команда по умолчанию (будет переопределена в docker-compose)

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

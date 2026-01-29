# auto_check_list — минимальный образ для Django + Celery
# - Multi-stage: в финале нет Poetry, gcc, libpq-dev — только runtime (libpq5, netcat, gosu)
# - Безопасность: приложение запускается от пользователя app (gosu), не root
# - Суперпользователь: при первом запуске создаётся, если заданы DJANGO_SUPERUSER_* в .env
# =============================================================================
# Stage 1: builder — установка зависимостей, экспорт requirements
# =============================================================================
FROM python:3.13-slim AS builder

WORKDIR /build

# Только для сборки (не попадают в итоговый образ)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root \
    && poetry export -f requirements.txt --without-hashes -o requirements.txt

# =============================================================================
# Stage 2: runtime — минимальный образ без poetry и компиляторов
# =============================================================================
FROM python:3.13-slim AS runtime

# Метаданные образа
LABEL maintainer="auto_check_list"

# Только runtime-зависимости (минимальный набор)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# gosu — переключение на non-root без лишних пакетов
COPY --from=tianon/gosu:1.19 /usr/local/bin/gosu /usr/local/bin/gosu
RUN chmod +x /usr/local/bin/gosu

# Непривилегированный пользователь (безопасность)
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

# Копируем только requirements из builder, ставим зависимости (в /usr/local — доступно всем)
COPY --from=builder /build/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Код приложения
COPY --chown=app:app . .

# Entrypoint — от root, т.к. нужен nc и доступ к БД при старте; приложение запускается от app
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN mkdir -p /app/static && chown -R app:app /app/static

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

EXPOSE 8000

# Entrypoint выполняется от root (миграции, суперпользователь); приложение — от app через gosu
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

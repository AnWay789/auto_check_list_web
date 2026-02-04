#!/bin/bash
set -e

# Ожидание готовности базы данных
echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Database is ready!"

# Ожидание готовности Redis
echo "Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 0.1
done
echo "Redis is ready!"

# Выполнение миграций
if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "Running migrations..."
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput
fi

# Сбор статики (если нужно)
# python manage.py collectstatic --noinput

# Создаем суперпользователя для админки (встроенная команда Django корректно хеширует пароль)
echo "Проверка суперпользователя..."
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Создание суперпользователя $DJANGO_SUPERUSER_USERNAME..."
    python manage.py createsuperuser \
        --noinput \
        --username "$DJANGO_SUPERUSER_USERNAME" \
        --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" \
        || echo "Суперпользователь уже существует или ошибка (пропускаем)"
else
    echo "Переменные DJANGO_SUPERUSER_USERNAME/PASSWORD не установлены"
fi

# Выполнение команды, переданной в качестве аргументов
exec "$@"

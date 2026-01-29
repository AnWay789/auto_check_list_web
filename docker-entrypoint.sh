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

# Миграции
echo "Running migrations..."
python manage.py migrate --noinput

# Создание суперпользователя при первом запуске (переменные из .env, пароль не в shell)
if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
  echo "Creating superuser if needed..."
  python scripts/create_superuser_if_missing.py || true
fi

# Запуск переданной команды от непривилегированного пользователя app
exec gosu app "$@"

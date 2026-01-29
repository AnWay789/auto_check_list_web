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
echo "Running migrations..."
python manage.py migrate --noinput

# Сбор статики (если нужно)
# python manage.py collectstatic --noinput

# Выполнение команды, переданной в качестве аргументов
exec "$@"

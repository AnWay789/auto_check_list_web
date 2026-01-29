#!/usr/bin/env python
"""
Создаёт суперпользователя Django при первом запуске, если заданы переменные
DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD и суперпользователей ещё нет.
Пароль читается из окружения, без передачи через shell — безопасно для спецсимволов.
"""
import os
import sys


def main():
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

    if not username or not password:
        return

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    User = get_user_model()

    if User.objects.filter(is_superuser=True).exists():
        print("Superuser already exists.")
        return

    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superuser created.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"create_superuser_if_missing: {e}", file=sys.stderr)
        sys.exit(1)

# Автоматизированный чеклист дашбордов для проверки L1

Система автоматизированной проверки дашбордов через [Telegram-бота](https://github.com/AnWay789/auto_check_list_bot). Django-бэкенд по расписанию отправляет списки дашбордов в бота; каждый дашборд имеет ссылку для отслеживания переходов (редирект на реальный дашборд).

## Содержание

- [Требования](#требования)
- [Инструкция по запуску](#инструкция-по-запуску)
- [Запуск через Docker](#запуск-через-docker)
- [Локальный запуск (без Docker)](#локальный-запуск-без-docker)
- [Архитектура](#архитектура)
- [Переменные окружения](#переменные-окружения)
- [Настройка периодической задачи](#настройка-периодической-задачи)
- [API для интеграции с Telegram-ботом](#api-для-интеграции-с-telegram-ботом)
- [Модели данных и задачи Celery](#модели-данных-и-задачи-celery)

---

## Требования

| Среда | Требования |
|-------|------------|
| **Python** | 3.13+ |
| **Менеджер зависимостей** | [Poetry](https://python-poetry.org/) |
| **Брокер для Celery** | Redis |
| **База данных** | PostgreSQL (в Docker) или SQLite (локально без `DATABASE_URL`) |

Для запуска через Docker нужны только [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/).

---

## Инструкция по запуску

### Вариант 1: Всё в Docker (рекомендуется)

1. **Клонируйте репозиторий и перейдите в каталог проекта.**

2. **Создайте общий `.env` в родительской директории** (каталог, содержащий оба проекта: `auto_check_list` и `auto_check_list_bot`):
   ```bash
   cd /path/to/puls   # родительская директория обоих проектов
   cp auto_check_list/.env.example .env
   ```

3. **Отредактируйте `.env`:**
   - При необходимости настройте `POSTGRES_*`, `DEBUG`, `ALLOWED_HOSTS`.
   - Для работы Telegram-бота в Docker задайте `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`.
   - Если бот поднимается в том же `docker-compose`, укажите путь к проекту бота в **`TELEGRAM_PJ_PATH`** (каталог с `Dockerfile`/кодом бота).  
     Пример: `TELEGRAM_PJ_PATH=./auto_check_list_bot`

4. **Запуск.** Выполняйте `docker-compose` из каталога `auto_check_list`. При указании в `docker-compose.yml` строки `env_file: ../.env` переменные будут браться из общего `.env` в родительской директории.

   **Запуск только бэкенда (Django + Celery + Redis + PostgreSQL), без бота:**
   ```bash
   docker-compose up -d redis db web celery_worker celery_beat
   ```

   **Запуск с Telegram-ботом** (нужен настроенный `TELEGRAM_PJ_PATH` в общем `.env` в родительской директории):
   ```bash
   docker-compose up -d --build
   ```

5. **Создайте суперпользователя Django:**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

6. **Откройте в браузере:**
   - Приложение: http://localhost:8000  
   - Админка: http://localhost:8000/admin/  

Миграции выполняются автоматически при старте контейнера `web` (см. `docker-entrypoint.sh`).

---

### Вариант 2: Локально (Poetry + Redis)

1. **Установите Redis** и запустите его (например, `redis-server`).

2. **Установите зависимости:**
   ```bash
   poetry install
   ```

3. **Активируйте окружение и перейдите в каталог проекта:**
   ```bash
   poetry shell
   cd /path/to/auto_check_list
   ```

4. **Опционально:** убедитесь, что в родительской директории (содержащей оба проекта) есть общий `.env` (см. шаг 2). При необходимости задайте там `DATABASE_URL` для PostgreSQL.  
   Без `DATABASE_URL` используется **SQLite** (`db.sqlite3` в корне проекта).

5. **Миграции и суперпользователь:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **В трёх отдельных терминалах запустите:**

   **Терминал 1 — Django:**
   ```bash
   python manage.py runserver
   ```

   **Терминал 2 — Celery worker:**
   ```bash
   celery -A config worker -l info
   ```

   **Терминал 3 — Celery beat:**
   ```bash
   celery -A config beat -l info
   ```

7. Админка: http://127.0.0.1:8000/admin/

Для локального запуска по умолчанию используются:
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/1`

---

## Запуск через Docker

### Основные команды

```bash
# Сборка и запуск всех сервисов
docker-compose up -d --build

# Только бэкенд (без Telegram-бота)
docker-compose up -d redis db web celery_worker celery_beat

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down

# Остановка с удалением volumes (очистка данных)
docker-compose down -v
```

### Полезные команды внутри контейнеров

```bash
# Суперпользователь
docker-compose exec web python manage.py createsuperuser

# Миграции вручную
docker-compose exec web python manage.py migrate

# Логи по сервисам
docker-compose logs -f web
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat
docker-compose logs -f redis
```

### Порты и сервисы

| Сервис        | Порт  | Описание                    |
|---------------|-------|-----------------------------|
| **web**       | 8000  | Django                      |
| **telegram_bot** | 8001  | API бота (если запущен)     |
| **Redis**     | 6379  | Брокер Celery               |
| **PostgreSQL**| 5432  | База данных                 |

### Запуск с Telegram-ботом в Docker

Сервис `telegram_bot` в `docker-compose.yml` собирается из отдельного проекта. В **общем `.env` в родительской директории** (каталог, содержащий `auto_check_list` и `auto_check_list_bot`) нужно указать:

- **`TELEGRAM_PJ_PATH`** — путь к каталогу проекта Telegram-бота (содержит `Dockerfile` и код бота).
- **`TELEGRAM_BOT_TOKEN`** и **`TELEGRAM_CHAT_ID`** — для работы бота.

Если `TELEGRAM_PJ_PATH` не задан или бот не нужен, используйте запуск без этого сервиса:

```bash
docker-compose up -d redis db web celery_worker celery_beat
```

---

## Локальный запуск (без Docker)

Краткая последовательность:

1. Redis запущен.
2. `poetry install` → `poetry shell`.
3. При необходимости скопировать и настроить общий `.env` в родительской директории (для PostgreSQL задать `DATABASE_URL`).
4. `python manage.py migrate` и `python manage.py createsuperuser`.
5. В трёх терминалах: `runserver`, `celery -A config worker -l info`, `celery -A config beat -l info`.

Без `DATABASE_URL` используется SQLite. Для Celery обязателен Redis.

---

## Архитектура

- **Django** — API, админка, модели дашбордов и событий проверки.
- **Celery** — фоновые и периодические задачи (отправка дашбордов в бота).
- **Celery Beat** — расписание (используется django-celery-beat, расписание хранится в БД).
- **Redis** — брокер и backend для Celery.
- **Telegram-бот** — отдельный сервис: получает дашборды от Django и отправляет их в чат.

---

## Переменные окружения

Основные переменные (полный пример — в `.env.example` в корне проекта или в родительской директории):

| Переменная | Описание | По умолчанию (локально) |
|------------|----------|--------------------------|
| `DEBUG` | Режим отладки Django | `True` |
| `SECRET_KEY` | Секретный ключ Django | см. `.env.example` |
| `ALLOWED_HOSTS` | Разрешённые хосты | `localhost,127.0.0.1` |
| `DATABASE_URL` | URL БД (PostgreSQL) | не задано → SQLite |
| `CELERY_BROKER_URL` | Redis для Celery | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis для результатов | `redis://localhost:6379/1` |
| `DJANGO_URL` | Внутренний URL Django (для callback) | `localhost:8000` |
| `DJANGO_EXTERNAL_URL` | Внешний URL (для ссылок в сообщениях) | `localhost:8000` |
| `TELEGRAM_URL` | URL API Telegram-бота | `localhost:8001` |
| `TELEGRAM_BOT_TOKEN` | Токен бота | — |
| `TELEGRAM_CHAT_ID` | ID чата для уведомлений | — |
| `TELEGRAM_PJ_PATH` | Путь к проекту бота (только для Docker) | — |

---

## Настройка периодической задачи

Чтобы дашборды автоматически уходили в бота по расписанию:

1. Запустите Django и зайдите в админку: http://127.0.0.1:8000/admin/
2. **Periodic tasks** → **Periodic tasks** → **Add periodic task**.
3. Укажите:
   - **Name**: например, `Send dashboard notifications`
   - **Task**: `check_list.tasks.start_send_dashboard_notification`
   - **Interval**: выберите или создайте интервал (например, каждые 5 минут) в **Intervals**.
   - **Enabled**: включено.
4. Сохраните.

В **Intervals** можно создать интервал: **Every** = `5`, **Period** = `minutes`.

---

## API для интеграции с Telegram-ботом

### Отправка дашбордов в бота (Django → бот)

Django отправляет POST-запрос боту:

- **URL**: `http://{TELEGRAM_URL}/api/checks/send` (задаётся в `check_list.settings.SEND_MESSAGE_ENDPOINT`)
- **Метод**: `POST`
- **Content-Type**: `application/json`

**Тело запроса (пример):**

```json
{
  "dashboards": [
    {
      "event_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "dashboard_uid": "dashboard-123",
      "name": "Sales Dashboard",
      "real_url": "https://example.com/dashboards/sales",
      "fake_url": "http://localhost:8000/api/to_dashboard/550e8400-e29b-41d4-a716-446655440000/",
      "time_for_check": 30
    }
  ]
}
```

### Callback результата проверки (бот → Django)

Бот отправляет результат проверки в Django:

- **URL**: `http://{DJANGO_URL}/api/dashbord_colback/`
- **Метод**: `POST`
- **Content-Type**: `application/json`

**Тело запроса:**

```json
{
  "event_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "problem": false
}
```

**Успешный ответ:** `{"status": "success"}`  
**Ошибка:** `{"status": "error", "message": "..."}`

### Редирект на дашборд (переход по fake_url)

- **URL**: `http://{DJANGO_URL}/api/to_dashboard/{event_uuid}/`
- **Метод**: `GET`

Устанавливает `checked = True`, записывает `check_time` и делает редирект на реальный URL дашборда.

---

## Модели данных и задачи Celery

### Основные модели

- **Dashboard** — `uid`, `name`, `url`, `time_for_check`.
- **CheckListItem** — привязка к дашборду, `description`, `interval` (django-celery-beat), `is_active`, `start_at`.
- **CheckEvents** — `uuid`, `dashboard`, `event_time`, `check_time`, `checked`, `problem` (из callback).

### Задачи Celery

- **`check_list.tasks.start_send_dashboard_notification`** — периодическая задача: проверяет активные элементы чек-листа, создаёт события, формирует батч дашбордов и вызывает отправку в бота, обновляет `start_at`.
- **`check_list.tasks.send_dashboard_notification`** — отправка списка дашбордов в бота по HTTP.
- **`check_list.tasks.debug_task`** — тестовая задача для проверки Celery.

### Проверка Celery

```bash
# В одном терминале: Redis, Django, Celery worker
# В другом:
python manage.py shell
```

```python
from check_list.tasks import debug_task
debug_task.delay("Test message from Django shell")
```

В логах worker должно появиться выполнение задачи.

---

## Админка Django

В админке доступны:

- **Dashboards** — дашборды
- **Check List Items** — элементы чек-листа
- **Check Events** — события проверок
- **Periodic tasks** — периодические задачи Celery (django-celery-beat)

Настройки Telegram в коде: `check_list/settings.py` — `TELEGRAM_URL`, `SEND_MESSAGE_ENDPOINT`.

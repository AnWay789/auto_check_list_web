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
   Для сбора метрик DNS/TCP в Lighthouse при локальном запуске один раз выполните:
   `playwright install chromium`.

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
2. `poetry install` → `poetry shell`. Для метрик Lighthouse (dns_ms, tcp_ms) один раз: `playwright install chromium`.
3. При необходимости скопировать и настроить общий `.env` в родительской директории (для PostgreSQL задать `DATABASE_URL`).
4. `python manage.py migrate` и `python manage.py createsuperuser`.
5. В трёх терминалах: `runserver`, `celery -A config worker -l info`, `celery -A config beat -l info`.

Без `DATABASE_URL` используется SQLite. Для Celery обязателен Redis.

---

## Архитектура

- **Django** — API, админка, модели дашбордов, событий проверки, Redash, Lighthouse, заказов с ошибками (order_errors).
- **Celery** — фоновые и периодические задачи: отправка дашбордов в бота, обновление запросов Redash, синхронизация заказов с ошибками и отправка в Наумен, запуск Lighthouse.
- **Celery Beat** — расписание (django-celery-beat, хранится в БД).
- **Redis** — брокер и backend для Celery.
- **Telegram-бот** — отдельный сервис: получает дашборды от Django и отправляет их в чат; по нажатию кнопки шлёт колбэк с результатом проверки и временем нажатия.

---

## Переменные окружения

Основные переменные (полный пример — в `.env.example` в корне проекта или в родительской директории):

| Переменная | Описание | По умолчанию (локально) |
|------------|----------|--------------------------|
| `DEBUG` | Режим отладки Django; при включении отправка результатов Lighthouse в ELK отключается | `True` |
| `SECRET_KEY` / `DJANGO_SECRET_KEY` | Секретный ключ Django | см. `.env.example` (в коде используется `DJANGO_SECRET_KEY`) |
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
| `ELK_INDEX_TEMPLATE` | Шаблон имени индекса ELK (поддерживает strftime, напр. `lighthouse-results-%Y-%m-%d`) | `lighthouse-results-%Y-%m-%d` |
| `REDASH_*`, `NAUMEN_*` | Опционально: ключи API Redash и Naumen для синхронизации заказов с ошибками и отправки в Наумен | — |

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

- **URL**: `http://{DJANGO_URL}/acl_api/dashbord_colback/`
- **Метод**: `POST`
- **Content-Type**: `application/json`

**Тело запроса:**

```json
{
  "event_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "problem": false,
  "date_time": "2026-03-03T12:00:00Z"
}
```

Поле `date_time` (ISO 8601, UTC) — время нажатия кнопки в боте; при отсутствии подставляется текущее время на сервере.

**Успешный ответ:** `{"status": "success"}`  
**Ошибка:** `{"status": "error", "message": "..."}`

### Редирект на дашборд (переход по fake_url)

- **URL**: `http://{DJANGO_URL}/acl_api/to_dashboard/{event_uuid}/`
- **Метод**: `GET`

Устанавливает `checked = True`, записывает `check_time` и делает редирект на реальный URL дашборда.

---

## Модели данных и задачи Celery

### Основные модели

- **Dashboard** — `uid`, `name`, `url`, `time_for_check`.
- **CheckListItem** — привязка к дашборду, `description`, `interval` (django-celery-beat), `is_active`, `start_at`.
- **CheckEvents** — `uuid`, `dashboard`, `event_time`, `check_time`, `button_click_time`, `no_problem`, `checked`. Время в БД хранится в UTC; в колбэке от бота передаётся `date_time` (UTC) и приводится к таймзоне приложения.

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

- **Dashboards** — дашборды чек-листа
- **Check List Items** — элементы чек-листа (расписание проверок)
- **Check Events** — события проверок (время события, нажатия кнопки, перехода по ссылке; экспорт в Excel)
- **Order errors** — заказы с ошибками (синхронизация с Redash, отправка в Наумен)
- **Redash** — дашборды Redash, SQL-запросы, запущенные запросы
- **Lighthouse** — источники и расписание проверок Lighthouse
- **Periodic tasks** — периодические задачи Celery (django-celery-beat)

Настройки Telegram: `check_list/settings.py` — `TELEGRAM_URL`, `SEND_MESSAGE_ENDPOINT`.

---

## HTTP API

### NinjaAPI инстансы

- `acl_api` — основной API для чек-листа и интеграции с Telegram-ботом.
- `oe_api` — API для работы с заказами с 400‑ми ошибками.

В `[config/urls.py](auto_check_list/config/urls.py)`:

```python
from api.api_app import acl_api, oe_api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", acl_api.urls),
    path("oe_api/", oe_api.urls),
]
```

Итоговые базовые URL:

- `acl_api`: `http://{DJANGO_URL}/api/`
- `oe_api`: `http://{DJANGO_URL}/oe_api/`

### Эндпоинты `acl_api`

#### 1. Callback от Telegram-бота

```python
@acl_api.post("/dashbord_colback/")
def get_check_list(request, payload: CheckListColback)
```

- **URL**: `POST http://{DJANGO_URL}/api/dashbord_colback/`
- **Тело запроса**:

```json
{
  "event_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "problem": false,
  "date_time": "2026-03-03T12:00:00Z"
}
```

- **Ответы**:
  - `200 {"status": "success"}` — колбэк принят, событие обновлено.
  - `400 {"status": "error", "message": "Invalid event UUID"}` — неверный UUID.
  - `404 {"status": "error", "message": "Event not found"}` — событие не найдено.
  - `500 {"status": "error", "message": "Internal server error"}` — непредвиденная ошибка.

#### 2. Переход на дашборд по fake_url

```python
@acl_api.get("/to_dashboard/{event_uuid}/")
def to_dashboard(request, event_uuid: str)
```

- **URL**: `GET http://{DJANGO_URL}/api/to_dashboard/{event_uuid}/`
- Поведение:
  - Помечает событие как просмотренное (`checked = True`, `check_time = now()`).
  - Делает `302`‑редирект на URL из `event.dashboard.url`.
- Ошибки:
  - `Http404("Invalid event UUID")` — неверный формат UUID.
  - `Http404("Event not found")` — событие не найдено.
  - `500 {"status": "error", "message": "Internal server error"}` — логируем ошибку и возвращаем JSON.

### Эндпоинты `oe_api` (заказы с 400‑ми ошибками)

Хэндлеры определены в `[api/handlers/order_error.py](auto_check_list/api/handlers/order_error.py)`.

#### 1. Заказ переоформлён

```python
@oe_api.patch("/order_error/{number}/reissue/")
def patch_order_error_reissue(request, number: int)
```

- **URL**: `PATCH http://{DJANGO_URL}/oe_api/order_error/{number}/reissue/`
- **Пример**:

```bash
curl -X PATCH http://localhost:8000/oe_api/order_error/1120817796/reissue/
```

- Поведение:
  - Ищет запись `OrderError` по полю `number`.
  - Устанавливает `has_been_reissued = True`.
  - Сохраняет запись.
- Ответы:
  - `200 {"status": "success"}` — успешное обновление.
  - `404 {"status": "error", "message": "Order not found"}` — заказ не найден.

#### 2. Заказ не был переоформлён

```python
@oe_api.patch("/order_error/{number}/not_reissue/")
def patch_order_error_not_reissue(request, number: int)
```

- **URL**: `PATCH http://{DJANGO_URL}/oe_api/order_error/{number}/not_reissue/`
- Поведение:
  - Аналогично предыдущему эндпоинту, но устанавливает `has_been_reissued = False`.
- Ответы:
  - `200 {"status": "success"}`.
  - `404 {"status": "error", "message": "Order not found"}`.

---

## Работа с 400‑ми ошибками заказов и `RecommendedAction`

### Поток данных 400‑х ошибок

1. **Получение из Redash**  
   Класс `RedashNaumenSync` в `[order_errors/redash_naumen_sync.py](auto_check_list/order_errors/redash_naumen_sync.py)`:

   - `_collect_orders(dashboard_id)` — берёт из Redash последнюю успешную выборку, валидирует строки через `RawOrderError` (pydantic) и группирует по номеру заказа.
   - `_filter_existing(raw_orders)` — отбрасывает уже сохранённые заказы, агрегирует по номеру:
     - `_build_order_error_base(first_item)` — базовый pydantic‑`OrderError`.
     - `_build_products_and_total(raw_order_items)` — формирует:
       - человекочитаемые строки позиций `products: list[str]`,
       - сумму заказа `order_total: float`,
       - «сырые» данные по товарам `raw_products: list[dict]` (GUID, имя, код, цена, остатки, статус).
     - заполняет `order_error.products`, `order_error.order_sum`, `order_error.raw_products`.
     - вызывает `_build_recommended_action(order_error, products)` — построение рекомендации.
   - `_save_orders(clear_orders)` — сохраняет агрегированные ошибки в Django‑модель `OrderError` (таблица `order_errors_ordererror`), учитывая фильтры `Filters`.

2. **Отправка в Наумен**  
   - `_get_error_order()` — читает `OrderErrorModel` с `is_send_to_naumen=False` и `can_send_to_naumen=True`, собирает `NaumenErrorRequest` с описанием ошибок и рекомендациями.
   - `_send_to_naumen()` — отправляет кейсы через `NaumenClient`, помечает заказы как отправленные.

### Модели для 400‑х ошибок

- **`OrderError` (Django)** — `[order_errors/models.py](auto_check_list/order_errors/models.py)`:
  - Поля: `number`, `order_date`, `customer_name`, `customer_phone`, `rk_name`, `store_address`, `store_id`,
    `raw_products` (JSON), `products` (текст), `order_sum`, `error`, `recommended_action`,
    `is_send_to_naumen`, `can_send_to_naumen`, `has_been_reissued`.

- **`OrderError` / `RawOrderError` (pydantic)** — `[order_errors/schemas/order_error.py](auto_check_list/order_errors/schemas/order_error.py)`:
  - `RawOrderError` описывает «сырые» поля из Redash (`ts`, `pr_guid`, `pr_name`, `pr_code`, `price`, `ordered_qty`, `stock_qty`, `ecom_qty`, `stock_status` и т.д.).
  - `OrderError` — агрегированное представление заказа для внутренних расчётов (`products`, `raw_products`, `order_sum`, `error`, `recommended_action`).

### `RecommendedAction` — шаблонные рекомендации для КЦ

Модель `[order_errors/models.py](auto_check_list/order_errors/models.py)`:

- Поля:
  - `triger_field` — какое поле заказа проверяется (`error`, `products`, `order_sum`, `customer_name` и т.п.).
  - `trigger` — подстрока, при наличии которой правило срабатывает.
  - `recommended_action` — шаблон текста рекомендации.
  - `custom_values` — JSON‑словарь с дополнительными значениями для подстановки.
  - `fail_values` — (если используется) набор значений, при которых подстановка из заказа считается «неуспешной» и используется fallback из `custom_values`.

- Поддерживаемые плейсхолдеры в `recommended_action`:

  - Стандартные поля заказа:  
    `{number}`, `{customer_name}`, `{customer_phone}`, `{rk_name}`, `{store_address}`, `{store_id}`, `{products}`, `{order_sum}`, `{error}`.
  - Специальный плейсхолдер **`{product}`**:
    - Работает для ошибок формата:
      ```python
      {"<GUID>": "Заказанное количество превышает допустимый остаток."}
      ```
    - Модель берёт GUID из `error`, ищет его в `order.raw_products` по `product_guid` и подставляет `product_name` товара.
  - Пользовательские переменные из `custom_values`, если заданы.

- Логика подстановки (`RecommendedAction._set_varible_in_recommended_action`):

  1. Для каждого плейсхолдера в шаблоне:
     - если имя — `product`, вызывается `_get_problem_product_from_error(order)` (анализ `error` и `raw_products`);
     - иначе сначала берётся одноимённое поле из заказа (`getattr(order, name, None)`),
       при отсутствии или «неподходящем» значении — значение из `custom_values[name]` (fallback).
  2. Все найденные значения последовательно заменяют `{name}` в тексте рекомендации.

- Пример шаблона:

  ```text
  Требуется подобрать аналог товару {product} и переоформить заказ
  ```

  При ошибке количества и наличии соответствующей позиции в `raw_products` итоговый текст будет, например:

  ```text
  Требуется подобрать аналог товару Троксерутин гель д/наруж прим 2 % 100 г х1 и переоформить заказ
  ```

### Как добавить новое правило `RecommendedAction`

1. Откройте админку: `/admin/order_errors/recommendedaction/`.
2. Создайте новое правило:
   - `name` / `description` — для себя.
   - `triger_field` — например, `error`.
   - `trigger` — подстрока, по которой распознаётся тип ошибки (например, `Заказанное количество превышает допустимый остаток`).
   - `recommended_action` — текст шаблона с плейсхолдерами (`{product}`, `{store_address}` и т.п.).
   - `custom_values` — (опционально) JSON с fallback‑значениями для плейсхолдеров.
   - `is_active = True`.
3. При следующей синхронизации из Redash `RedashNaumenSync` автоматически применит это правило ко всем подходящим заказам. 

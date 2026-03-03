# Аудит проекта auto_check_list

**Дата актуализации:** 2025-02-19 (повторный аудит)

---

## 1. Критические ошибки

### 1.1. Неверный импорт в `redash/models.py`

**Файл:** `redash/models.py`, строка 14

**Проблема:** Используется `from utils.time import default_start_at`. В проекте нет пакета `utils` в корне — функция определена в `config/utils/time.py`. Импорт должен быть:

```python
from config.utils.time import default_start_at
```

Иначе при загрузке приложения `redash` возможен **ImportError** (если в `sys.path` нет каталога с модулем `utils.time`).

---

## 2. Исправлено с прошлого аудита

- **redash/tasks.py** — две задачи `start_redash_dashboards` и `start_redash_sqls`; в каждой цикл по объектам и вызов `start_query_by_crontab()` у экземпляра.
- **api/wrappers/naumen.py** — отправляются все кейсы, возвращается список ответов; при отсутствии учётных данных выбрасывается `ValueError`.
- **redash/models.py** — `UUIDField(default=uuid.uuid4, editable=False)`; импорт `timedelta`; `query` заменён на `TextField()`; `related_name` разведены (`redash_sql_crontab_items`, `redash_dashboard_crontab_items`); для `start_at` используется вызываемая функция `default_start_at`.
- **config/utils/time.py** — в `default_start_at` используется параметр `time_delta`: `timedelta(minutes=time_delta)`.
- **check_list/models.py**, **lighthouse/models.py** — для `start_at` используется `default=default_start_at` из `config.utils.time` (вычисляется при создании объекта).

---

## 3. Важные замечания

### 3.1. Загрузка `.env` от текущей директории

**Файл:** `config/settings.py`, строки 21–23

`load_dotenv('../.env')` зависит от текущей рабочей директории. При запуске из другой папки (Celery, WSGI, корень репозитория) файл может не найтись.

**Рекомендация:** Привязать путь к проекту:

```python
load_dotenv(BASE_DIR.parent / '.env')
# или, если .env в корне проекта (рядом с config/):
load_dotenv(BASE_DIR / '.env')
```

---

### 3.2. Логгер через `Logger(__name__)` в моделях

**Файлы:** `check_list/models.py` (стр. 12), `redash/models.py` (стр. 16)

Используется `logger = Logger(__name__)`. Для единообразия и иерархии логгеров лучше везде использовать `logging.getLogger(__name__)` (как в `lighthouse`, `order_errors`, задачах Celery).

---

### 3.3. `OrderError.clear_old` — только для одного объекта

**Файл:** `order_errors/models.py`

`clear_old(days=2)` — метод экземпляра, удаляет только сам объект при выполнении условия. Для массовой очистки старых записей удобнее метод менеджера или отдельная команда/задача:

```python
OrderError.objects.filter(
    order_date__lt=timezone.now() - timezone.timedelta(days=days)
).delete()
```

---

### 3.4. Опечатка в комментарии Naumen

**Файл:** `order_errors/redash_naumen_sync.py` (в тексте для Наумен)

В комментарии к кейсу используется строка «Позции в заказе» — по смыслу скорее «Позиции в заказе». Не влияет на работу, только на отображение в Наумен.

---

## 4. Конфигурация и окружение

### 4.1. Production

- **SECRET_KEY** по умолчанию `"django-insecure-default-key"` — в production задавать уникальный ключ через переменную окружения.
- **DEBUG** по умолчанию `"True"` — в production отключать.

### 4.2. Интеграции

Переменные REDASH_*, NAUMEN_*, ELK_* опциональны; при их отсутствии возможны `None` и ошибки при вызове API. Имеет смысл описать в README, какие переменные обязательны для каких сценариев.

---

## 5. Миграции и приложения

### 5.1. Приложение `order_errors`

- В `INSTALLED_APPS` приложение указано.
- В каталоге `order_errors/migrations/` **нет файлов миграций**. Нужно выполнить:
  - `python manage.py makemigrations order_errors`
  - `python manage.py migrate`

### 5.2. Два приложения с моделью `CheckListItem`

Модель `CheckListItem` есть в `check_list` и в `lighthouse` (разная семантика: дашборды и источники Lighthouse). Конфликта имён нет; при импортах и в Celery-задачах важно не путать приложения.

---

## 6. Тесты

В проекте не найдено тестов (по шаблону `**/test*.py`). Рекомендуется добавить тесты для:

- задач Celery (redash, order_errors, check_list, lighthouse);
- логики синка и отправки в Наумен (order_errors);
- API (Django Ninja).

---

## 7. Резюме

| Категория             | Состояние |
|-----------------------|-----------|
| Критические ошибки   | **1** (импорт `utils.time` в redash — должен быть `config.utils.time`) |
| Важные замечания      | **4** (load_dotenv, логгеры, clear_old, опечатка «Позции») |
| Уже исправлено       | redash tasks, naumen, redash UUID/query/related_name/default_start_at, time_delta, start_at в check_list и lighthouse |

**В первую очередь исправить:**

1. **redash/models.py** — заменить `from utils.time import default_start_at` на `from config.utils.time import default_start_at`.

**Далее:** загрузка `.env` от `BASE_DIR`, логгеры в моделях через `logging.getLogger`, миграции для `order_errors`, при необходимости — метод массовой очистки для `OrderError` и правка опечатки «Позции».

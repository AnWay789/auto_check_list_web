# Развёртывание в продакшене (PROD_SETUP)

Подробная пошаговая инструкция по выводу проекта **auto_check_list** на сервер и обеспечению доступа из интернета с HTTPS.

---

## Содержание

1. [Требования и обзор](#1-требования-и-обзор)
2. [Подготовка сервера](#2-подготовка-сервера)
3. [Установка Docker и Docker Compose](#3-установка-docker-и-docker-compose)
4. [Установка Nginx](#4-установка-nginx)
5. [Установка Certbot (Let's Encrypt)](#5-установка-certbot-lets-encrypt)
6. [Настройка файрвола](#6-настройка-файрвола)
7. [Домен (если используется)](#7-домен-если-используется)
8. [Клонирование проекта и настройка .env](#8-клонирование-проекта-и-настройка-env)
9. [Запуск приложения в продакшене](#9-запуск-приложения-в-продакшене)
10. [Настройка Nginx как reverse proxy](#10-настройка-nginx-как-reverse-proxy)
11. [Получение SSL-сертификата (HTTPS)](#11-получение-ssl-сертификата-https)
12. [Первый вход и суперпользователь](#12-первый-вход-и-суперпользователь)
13. [Telegram-бот (опционально)](#13-telegram-бот-опционально)
14. [Безопасность и чеклист](#14-безопасность-и-чеклист)
15. [Резервное копирование](#15-резервное-копирование)
16. [Обновление приложения](#16-обновление-приложения)
17. [Полезные команды и устранение неполадок](#17-полезные-команды-и-устранение-неполадок)

---

## 1. Требования и обзор

### Что нужно до начала

| Что | Описание |
|-----|----------|
| **VPS или выделенный сервер** | Любой хостинг с Ubuntu 22.04 LTS (или 20.04): DigitalOcean, Timeweb, Selectel, REG.RU, и т.д. |
| **SSH-доступ** | Логин и пароль или SSH-ключ к серверу. |
| **Домен (рекомендуется)** | Для HTTPS и удобного доступа (например, `checklist.example.com`). Можно обойтись только IP. |
| **Минимум ресурсов** | 1 CPU, 1–2 GB RAM, 10–20 GB диск. |

### Что будет установлено на сервер

- **Docker** и **Docker Compose** — запуск приложения в контейнерах.
- **Nginx** — веб-сервер, приём трафика на 80/443 и проксирование на Django.
- **Certbot** — бесплатные SSL-сертификаты Let's Encrypt (для HTTPS).
- **UFW** — файрвол (открыты только нужные порты).

### Схема после настройки

```
Интернет → :443 (HTTPS) / :80 (HTTP) → Nginx → :8000 (Django в Docker)
                                         ↓
                              Статика, SSL-терминация
```

Redis и PostgreSQL работают только внутри Docker-сети и не открыты в интернет.

---

## 2. Подготовка сервера

### 2.1. Подключение по SSH

С вашего компьютера:

```bash
ssh root@IP_ВАШЕГО_СЕРВЕРА
```

Или с указанием ключа:

```bash
ssh -i ~/.ssh/your_key root@IP_ВАШЕГО_СЕРВЕРА
```

Замените `IP_ВАШЕГО_СЕРВЕРА` на реальный IP или домен.

### 2.2. Обновление системы

```bash
apt update && apt upgrade -y
```

### 2.3. Создание пользователя (необязательно, но рекомендуется)

Работа под `root` небезопасна. Создайте отдельного пользователя:

```bash
adduser deploy
usermod -aG sudo deploy
```

Скопируйте ваш SSH-ключ на сервер (выполнять **на вашем компьютере**):

```bash
ssh-copy-id deploy@IP_ВАШЕГО_СЕРВЕРА
```

Дальше можно подключаться так:

```bash
ssh deploy@IP_ВАШЕГО_СЕРВЕРА
```

В следующих шагах команды даны без `sudo` там, где вы уже вошли под `deploy` (тогда перед командами из раздела «Установка» нужно ставить `sudo`).

### 2.4. Установка базовых пакетов

```bash
sudo apt install -y curl git ca-certificates gnupg lsb-release
```

---

## 3. Установка Docker и Docker Compose

### 3.1. Репозиторий Docker (Ubuntu/Debian)

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
```

### 3.2. Установка Docker Engine

```bash
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 3.3. Проверка

```bash
sudo docker run hello-world
```

Должно вывести сообщение от Docker. Если используете пользователя `deploy`, добавьте его в группу `docker`, чтобы не писать `sudo` перед каждой командой:

```bash
sudo usermod -aG docker $USER
```

Выйдите из SSH и зайдите снова, чтобы группа применилась.

### 3.4. Проверка Docker Compose

```bash
docker compose version
```

Должна отобразиться версия (v2.x).

---

## 4. Установка Nginx

Nginx будет принимать запросы на портах 80 и 443 и передавать их в контейнер с Django (порт 8000).

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

Проверка:

```bash
sudo systemctl status nginx
```

В браузере откройте `http://IP_ВАШЕГО_СЕРВЕРА` — должна открыться страница Nginx по умолчанию. Позже мы заменим конфиг на наш.

---

## 5. Установка Certbot (Let's Encrypt)

Certbot нужен для бесплатного HTTPS-сертификата.

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Проверка:

```bash
certbot --version
```

Сам выпуск сертификата делается после настройки Nginx под ваш домен (см. раздел 11).

---

## 6. Настройка файрвола

Открываем только нужные порты: SSH (22), HTTP (80), HTTPS (443). Порт 8000 наружу не открываем — к нему обращается только Nginx с этого же сервера.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Проверка:

```bash
sudo ufw status verbose
```

Убедитесь, что 22, 80, 443 в статусе ALLOW.

---

## 7. Домен (если используется)

1. В панели управления доменом создайте **A-запись**:
   - Имя: `@` или поддомен (например, `checklist`).
   - Значение: **IP вашего сервера**.
   - TTL: 300–3600.

2. Подождите 5–30 минут, пока DNS обновится. Проверка:

   ```bash
   ping ваш-домен.com
   ```

   Должен отвечать IP сервера.

Если домена нет, всё равно можно работать по IP: тогда HTTPS через Let's Encrypt будет недоступен (сертификаты выдаются только на домены), но HTTP по IP будет работать.

---

## 8. Клонирование проекта и настройка .env

### 8.1. Каталог для приложения

```bash
sudo mkdir -p /var/www/auto_check_list
sudo chown $USER:$USER /var/www/auto_check_list
cd /var/www/auto_check_list
```

### 8.2. Клонирование репозитория

Подставьте ваш репозиторий (GitHub, GitLab, и т.д.):

```bash
git clone https://github.com/ВАШ_ОРГАНИЗАЦИЯ/auto_check_list.git .
```

Или загрузка архива:

```bash
# На вашем компьютере: собрать архив и загрузить на сервер
scp -r /путь/к/auto_check_list deploy@IP_СЕРВЕРА:/var/www/auto_check_list
```

На сервере убедитесь, что файлы лежат в `/var/www/auto_check_list` (в корне проекта должны быть `manage.py`, `docker-compose.yml`, `pyproject.toml`).

### 8.3. Файл .env для продакшена

Создайте файл `.env` в корне проекта (рядом с `docker-compose.yml`):

```bash
cd /var/www/auto_check_list
nano .env
```

Минимальный вариант (подставьте свои значения):

```env
# Режим и безопасность
DEBUG=False
SECRET_KEY=сгенерируйте-длинный-случайный-ключ-минимум-50-символов

# Хосты: IP сервера и/или домен
ALLOWED_HOSTS=123.45.67.89,checklist.example.com

# URL приложения (как пользователи заходят в браузер)
# С доменом и HTTPS (после настройки сертификата):
DJANGO_EXTERNAL_URL=https://checklist.example.com
# Или по IP без HTTPS:
# DJANGO_EXTERNAL_URL=http://123.45.67.89

# Внутри Docker (не менять)
DJANGO_URL=web:8000

# База данных (придумайте свой пароль)
POSTGRES_DB=auto_check_list
POSTGRES_USER=postgres
POSTGRES_PASSWORD=надежный-пароль-для-postgres
DATABASE_URL=postgresql://postgres:надежный-пароль-для-postgres@db:5432/auto_check_list

# Celery (внутри Docker)
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Telegram (если бот в том же docker-compose)
TELEGRAM_URL=telegram_bot:8001
TELEGRAM_BOT_TOKEN=ваш-токен-от-BotFather
TELEGRAM_CHAT_ID=id-чата-для-уведомлений
```

Как сгенерировать `SECRET_KEY` (на сервере или у себя в терминале):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Скопируйте вывод в `SECRET_KEY=` в `.env`.

Сохраните файл: в `nano` — `Ctrl+O`, Enter, затем `Ctrl+X`.

### 8.4. Проверка .env

Убедитесь, что файл читается и в нём нет лишних пробелов вокруг `=`:

```bash
cat .env
```

---

## 9. Запуск приложения в продакшене

Используется **production-override**: Gunicorn вместо `runserver`, Redis и PostgreSQL не пробрасываются на хост.

### 9.1. Сборка образов

```bash
cd /var/www/auto_check_list
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```

### 9.2. Запуск только бэкенда (без Telegram-бота)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d redis db web celery_worker celery_beat
```

Проверка:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Все перечисленные сервисы должны быть в состоянии `Up`. Логи:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f web
```

Остановка по `Ctrl+C` не останавливает контейнеры (они работают в фоне). Остановить всё:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

### 9.3. Проверка, что Django отвечает локально

На сервере:

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/
```

Ожидается код 200, 301 или 302. Если 200/302 — Nginx можно настраивать на `http://127.0.0.1:8000`.

---

## 10. Настройка Nginx как reverse proxy

Nginx будет принимать запросы на 80 (и позже 443) и проксировать их на контейнер `web` (порт 8000).

### 10.1. Создание конфига сайта

```bash
sudo nano /etc/nginx/sites-available/auto_check_list
```

Вставьте один из двух вариантов.

**Вариант A: с доменом** (подставьте свой домен):

```nginx
server {
    listen 80;
    server_name checklist.example.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /var/www/auto_check_list/static/;
    }
}
```

**Вариант B: только по IP** (замените `123.45.67.89` на IP сервера):

```nginx
server {
    listen 80 default_server;
    server_name 123.45.67.89;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /var/www/auto_check_list/static/;
    }
}
```

Сохраните файл.

### 10.2. Подключение сайта и отключение дефолтного

```bash
sudo ln -sf /etc/nginx/sites-available/auto_check_list /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

### 10.3. Проверка конфигурации и перезагрузка Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 10.4. Проверка в браузере

- С доменом: `http://checklist.example.com`
- По IP: `http://IP_ВАШЕГО_СЕРВЕРА`

Должна открыться главная страница Django или редирект на админку/логин.

---

## 11. Получение SSL-сертификата (HTTPS)

Этот шаг только если у вас настроен **домен** и он указывает на этот сервер.

### 11.1. Выпуск сертификата

```bash
sudo certbot --nginx -d checklist.example.com
```

Подставьте свой домен. Certbot спросит email — укажите реальный (для уведомлений о продлении). Согласитесь с условиями, при необходимости выберите «перенаправлять HTTP на HTTPS».

### 11.2. Проверка продления

Продление у Let's Encrypt автоматическое. Проверить таймер можно так:

```bash
sudo certbot renew --dry-run
```

### 11.3. Обновление .env после включения HTTPS

В `.env` должен быть внешний URL с `https`:

```env
DJANGO_EXTERNAL_URL=https://checklist.example.com
```

Перезапуск контейнеров после смены `.env`:

```bash
cd /var/www/auto_check_list
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d web celery_worker celery_beat
```

---

## 12. Первый вход и суперпользователь

### 12.1. Создание суперпользователя Django

```bash
cd /var/www/auto_check_list
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Введите логин, email и пароль.

### 12.2. Сбор статики (админка и статические файлы)

Чтобы админка и статика отдавались через Nginx, один раз выполните:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

Файлы появятся в каталоге `static/` в корне проекта; Nginx уже настроен раздавать их по URL `/static/`.

### 12.3. Вход в админку

В браузере откройте:

- С доменом: `https://checklist.example.com/admin/`
- По IP: `http://IP_ВАШЕГО_СЕРВЕРА/admin/`

Войдите под созданным суперпользователем. Дальше настройте дашборды и периодические задачи по **README** проекта.

---

## 13. Telegram-бот (опционально)

Если бот развёрнут в том же `docker-compose` и у вас есть отдельный репозиторий бота:

1. В `.env` задайте:
   - `TELEGRAM_PJ_PATH` — путь на сервере к каталогу с проектом Telegram-бота (с `Dockerfile` и кодом).
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

2. Запустите все сервисы, включая бота:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

Если бот работает на другом сервере или хосте, в `.env` укажите его URL в `TELEGRAM_URL` (например, `https://bot.example.com` без порта, если бот за Nginx на 443). Внутри Django в настройках должен использоваться этот же URL для отправки сообщений.

---

## 14. Безопасность и чеклист

- [ ] **DEBUG=False** в `.env`.
- [ ] **SECRET_KEY** уникальный, длинный, только в `.env`, не в репозитории.
- [ ] **ALLOWED_HOSTS** содержит только ваш домен и/или IP сервера.
- [ ] **POSTGRES_PASSWORD** сложный, не дефолтный.
- [ ] Порт **8000** не открыт в UFW (трафик только через Nginx).
- [ ] Порты **5432** и **6379** не открыты в интернет (в prod-override они не пробрасываются на хост).
- [ ] Для продакшена используется **Gunicorn** (через `docker-compose.prod.yml`), не `runserver`.
- [ ] При наличии домена настроен **HTTPS** (Certbot) и **DJANGO_EXTERNAL_URL** с `https://`.
- [ ] Токен и чат Telegram только в `.env`, не в коде и не в git.

---

## 15. Резервное копирование

### 15.1. База данных PostgreSQL

Дамп (на сервере):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db pg_dump -U postgres auto_check_list > backup_$(date +%Y%m%d_%H%M).sql
```

Восстановление:

```bash
cat backup_YYYYMMDD_HHMM.sql | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U postgres auto_check_list
```

### 15.2. Volumes Docker (данные Redis и PostgreSQL)

Расположение volumes можно посмотреть:

```bash
docker volume ls
```

Копирование volume целиком требует остановки контейнеров или использования утилит типа `restic`/`borg`. Для начала достаточно регулярных дампов БД (см. выше).

---

## 16. Обновление приложения

После выката нового кода на сервер:

```bash
cd /var/www/auto_check_list
git pull   # или загрузите файлы иначе

docker compose -f docker-compose.yml -f docker-compose.prod.yml build web celery_worker celery_beat
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d web celery_worker celery_beat
```

Миграции (если появились новые):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate --noinput
```

Сбор статики (если используете и меняли статику):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

И при необходимости обновите alias статики в Nginx (см. раздел 10).

---

## 17. Полезные команды и устранение неполадок

### Логи

```bash
# Все сервисы
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Только Django
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f web

# Celery worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f celery_worker

# Celery beat
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f celery_beat
```

### Статус контейнеров

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### Перезапуск одного сервиса

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart web
```

### Вход в контейнер Django

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web bash
# внутри: python manage.py shell, python manage.py migrate, и т.д.
```

### Ошибка 502 Bad Gateway

- Убедитесь, что контейнер `web` запущен: `docker compose ... ps`.
- Проверьте, что Django слушает 8000: `curl -I http://127.0.0.1:8000/` на сервере.
- Проверьте логи: `docker compose ... logs web` и `sudo tail -f /var/log/nginx/error.log`.

### Ошибка «DisallowedHost»

- В `.env` в `ALLOWED_HOSTS` должен быть домен или IP, с которого вы заходите (без `https://` и порта, через запятую при нескольких значениях).

### Ссылки в Telegram ведут не туда

- В `.env` задайте **DJANGO_EXTERNAL_URL** именно тем адресом, по которому пользователи открывают сайт в браузере (с `https://` и доменом, без слэша в конце). После изменения перезапустите `web`, `celery_worker`, `celery_beat`.

---

Если какой-то шаг не срабатывает на вашем окружении, сверьте версии Docker, Nginx и ОС и при необходимости адаптируйте команды под свою панель или хостинг-провайдера.

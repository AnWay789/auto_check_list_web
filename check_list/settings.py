import os

# URL телеграм бота. По умолчанию localhost:8001 для локальной разработки
# В Docker для доступа к боту на хосте используйте host.docker.internal:8001
TELEGRAM_URL = os.environ.get("TELEGRAM_URL", "localhost:8001")
SEND_MESSAGE_ENDPOINT = "/api/checks/send"

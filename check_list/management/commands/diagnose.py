from django.core.management.base import BaseCommand
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
import httpx
from check_list.models import Dashboard, CheckListItem, CheckEvents
from check_list.settings import TELEGRAM_URL, SEND_MESSAGE_ENDPOINT
from config.settings import DJANGO_EXTERNAL_URL


class Command(BaseCommand):
    help = 'Диагностика системы автоматизированного чеклиста дашбордов'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Диагностика системы ===\n'))
        
        # 1. Проверка дашбордов
        self.check_dashboards()
        
        # 2. Проверка элементов чек-листа
        self.check_checklist_items()
        
        # 3. Проверка периодических задач
        self.check_periodic_tasks()
        
        # 4. Проверка последних событий
        self.check_recent_events()
        
        # 5. Проверка доступности телеграм бота
        self.check_telegram_bot()
        
        # 6. Проверка настроек
        self.check_settings()
        
        self.stdout.write(self.style.SUCCESS('\n=== Диагностика завершена ==='))

    def check_dashboards(self):
        self.stdout.write(self.style.WARNING('\n1. Дашборды:'))
        dashboards = Dashboard.objects.all()
        if dashboards.exists():
            self.stdout.write(f'   Всего дашбордов: {dashboards.count()}')
            for dashboard in dashboards:
                self.stdout.write(f'   - {dashboard.name} (uid: {dashboard.uid}, url: {dashboard.url})')
        else:
            self.stdout.write(self.style.ERROR('   Нет дашбордов в базе данных!'))

    def check_checklist_items(self):
        self.stdout.write(self.style.WARNING('\n2. Элементы чек-листа:'))
        items = CheckListItem.objects.all()
        if items.exists():
            active_items = items.filter(is_active=True)
            inactive_items = items.filter(is_active=False)
            
            self.stdout.write(f'   Всего элементов: {items.count()}')
            self.stdout.write(f'   Активных: {active_items.count()}')
            self.stdout.write(f'   Неактивных: {inactive_items.count()}')
            
            if active_items.exists():
                self.stdout.write('\n   Активные элементы:')
                now = timezone.now()
                for item in active_items:
                    status = '✓ Готов к отправке' if item.start_at <= now else '⏳ Ожидает'
                    time_diff = item.start_at - now
                    if time_diff.total_seconds() > 0:
                        hours = int(time_diff.total_seconds() // 3600)
                        minutes = int((time_diff.total_seconds() % 3600) // 60)
                        time_str = f'через {hours}ч {minutes}м'
                    else:
                        time_str = 'просрочено'
                    
                    self.stdout.write(
                        f'   - {item.dashboard.name}: {status} '
                        f'(start_at: {item.start_at.strftime("%Y-%m-%d %H:%M:%S")}, {time_str})'
                    )
            else:
                self.stdout.write(self.style.ERROR('   Нет активных элементов чек-листа!'))
        else:
            self.stdout.write(self.style.ERROR('   Нет элементов чек-листа в базе данных!'))

    def check_periodic_tasks(self):
        self.stdout.write(self.style.WARNING('\n3. Периодические задачи Celery:'))
        tasks = PeriodicTask.objects.filter(enabled=True)
        target_task = 'check_list.tasks.start_send_dashboard_notification'
        
        if tasks.exists():
            self.stdout.write(f'   Всего активных задач: {tasks.count()}')
            found = False
            for task in tasks:
                if task.task == target_task:
                    found = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'   ✓ Задача "{target_task}" найдена и активна'
                        )
                    )
                    if task.interval:
                        self.stdout.write(f'      Интервал: каждые {task.interval.every} {task.interval.period}')
                    if task.crontab:
                        self.stdout.write(f'      Расписание: {task.crontab}')
                    self.stdout.write(f'      Последний запуск: {task.last_run_at or "Никогда"}')
                    break
            
            if not found:
                self.stdout.write(
                    self.style.ERROR(
                        f'   ✗ Задача "{target_task}" не найдена или неактивна!'
                    )
                )
                self.stdout.write('   Доступные задачи:')
                for task in tasks:
                    self.stdout.write(f'   - {task.task} ({task.name})')
        else:
            self.stdout.write(
                self.style.ERROR('   Нет активных периодических задач!')
            )

    def check_recent_events(self):
        self.stdout.write(self.style.WARNING('\n4. Последние события:'))
        events = CheckEvents.objects.order_by('-event_time')[:10]
        if events.exists():
            self.stdout.write(f'   Последние {events.count()} событий:')
            for event in events:
                checked_status = '✓' if event.checked else '✗'
                problem_status = '⚠ Проблема' if event.problem else '✓ OK'
                self.stdout.write(
                    f'   {checked_status} {event.dashboard.name} '
                    f'({event.event_time.strftime("%Y-%m-%d %H:%M:%S")}) - {problem_status}'
                )
        else:
            self.stdout.write('   Нет событий в базе данных')

    def check_telegram_bot(self):
        self.stdout.write(self.style.WARNING('\n5. Проверка доступности телеграм бота:'))
        url = f"http://{TELEGRAM_URL}{SEND_MESSAGE_ENDPOINT}"
        self.stdout.write(f'   URL: {url}')
        
        try:
            # Пробуем сделать простой запрос для проверки доступности
            with httpx.Client(timeout=5.0) as client:
                # Отправляем пустой запрос для проверки доступности
                # (бот может вернуть ошибку, но это покажет, что он доступен)
                try:
                    response = client.post(url, json={"dashboards": []}, timeout=5.0)
                    self.stdout.write(
                        self.style.SUCCESS(f'   ✓ Телеграм бот доступен (статус: {response.status_code})')
                    )
                except httpx.ConnectError:
                    self.stdout.write(
                        self.style.ERROR(
                            f'   ✗ Не удалось подключиться к телеграм боту по адресу {url}'
                        )
                    )
                    self.stdout.write('   Проверьте, что бот запущен и доступен по указанному адресу')
                except httpx.TimeoutException:
                    self.stdout.write(
                        self.style.ERROR('   ✗ Таймаут при подключении к телеграм боту')
                    )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ Ошибка при проверке: {str(e)}')
            )

    def check_settings(self):
        self.stdout.write(self.style.WARNING('\n6. Настройки:'))
        self.stdout.write(f'   DJANGO_EXTERNAL_URL: {DJANGO_EXTERNAL_URL}')
        self.stdout.write(f'   TELEGRAM_URL: {TELEGRAM_URL}')
        self.stdout.write(f'   SEND_MESSAGE_ENDPOINT: {SEND_MESSAGE_ENDPOINT}')
        
        # Проверка, что настройки разумные
        if 'localhost' in TELEGRAM_URL and 'host.docker.internal' not in TELEGRAM_URL:
            self.stdout.write(
                self.style.WARNING(
                    '   ⚠ TELEGRAM_URL использует localhost - может не работать из Docker контейнера'
                )
            )
            self.stdout.write('   Рекомендуется использовать host.docker.internal:8001 для бота на хосте')

"""
Импорт конфигов Lighthouse из YAML (формат autoLighthouse).
Создаёт записи Source для каждого URL; CheckListItem можно добавить вручную в админке.
"""
import logging
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from lighthouse.models import Source

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Импорт config.yaml (формат autoLighthouse): создаёт Source для каждого URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "config_path",
            nargs="?",
            default="config.yaml",
            type=str,
            help="Путь к YAML-файлу с configs",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Не создавать записи, только показать, что будет создано",
        )

    def handle(self, *args, **options):
        config_path = Path(options["config_path"])
        dry_run = options["dry_run"]

        if not config_path.exists():
            self.stderr.write(self.style.ERROR(f"Файл не найден: {config_path}"))
            return

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        configs = data.get("configs") or []
        created = 0

        for cfg in configs:
            urls = cfg.get("urls") or []
            metadata = cfg.get("metadata")
            if isinstance(metadata, str):
                metadata = {}
            elif metadata is None:
                metadata = {}
            headers = cfg.get("headers")
            if headers is None:
                headers = {}
            elif isinstance(headers, str):
                headers = {"Cookie": headers} if headers else {}

            for url in urls:
                if not url or not isinstance(url, str):
                    continue
                project = (metadata or {}).get("project", "")
                page_type = (metadata or {}).get("page_type", "")
                name = f"{project} {page_type}".strip() or url
                if len(name) > 100:
                    name = name[:97] + "..."

                if dry_run:
                    self.stdout.write(f"  [dry-run] Source: name={name!r}, url={url}")
                    created += 1
                    continue

                _, was_created = Source.objects.get_or_create(
                    url=url,
                    defaults={
                        "name": name,
                        "headers": headers,
                        "metadata": metadata,
                        "description": f"Импорт из {config_path}",
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"  Создан Source: {name} — {url}"))

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[dry-run] Будет создано/пропущено: {created} URL"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Импорт завершён. Создано новых: {created}"))

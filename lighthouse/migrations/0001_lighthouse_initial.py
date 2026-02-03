# Generated manually for lighthouse app

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("url", models.URLField()),
                ("headers", models.JSONField(blank=True, null=True)),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        null=True,
                        help_text="Произвольные метаданные для ELK (например project, page_type).",
                    ),
                ),
                ("description", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="CheckListItem",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("description", models.TextField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("start_at", models.DateTimeField()),
                (
                    "crontab",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="django_celery_beat.crontabschedule",
                    ),
                ),
                (
                    "interval",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="django_celery_beat.intervalschedule",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checklist_items",
                        to="lighthouse.source",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CheckEvents",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("event_time", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(blank=True, max_length=32, null=True)),
                (
                    "metrics",
                    models.JSONField(
                        blank=True,
                        null=True,
                        help_text="Метрики Lighthouse: fcp_ms, fcp_s, tbt_ms, tbt_s, si_ms, si_s, lcp_ms, lcp_s, cls.",
                    ),
                ),
                ("error_message", models.TextField(blank=True, null=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="check_events",
                        to="lighthouse.source",
                    ),
                ),
            ],
        ),
    ]

# Generated manually to fix missing fields and models

import django.db.models.deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('check_list', '0002_remove_checklistitem_scheduled_time_and_more'),
    ]

    operations = [
        # Add missing fields to Dashboard
        # First add uid as nullable, then make it unique
        migrations.AddField(
            model_name='dashboard',
            name='uid',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='dashboard',
            name='time_for_check',
            field=models.IntegerField(default=60, help_text='Время в минутах для проверки дашборда'),
        ),
        # Make uid unique after data migration (if needed)
        migrations.AlterField(
            model_name='dashboard',
            name='uid',
            field=models.CharField(max_length=128, unique=True),
        ),
        # Add missing field to CheckListItem
        migrations.AddField(
            model_name='checklistitem',
            name='start_at',
            field=models.DateTimeField(default='2026-01-27T00:00:00Z'),
            preserve_default=False,
        ),
        # Create CheckEvents model
        migrations.CreateModel(
            name='CheckEvents',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_time', models.DateTimeField(auto_now_add=True)),
                ('check_time', models.DateTimeField(blank=True, null=True)),
                ('problem', models.BooleanField(default=False)),
                ('checked', models.BooleanField(default=False)),
                ('dashboard', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history_dashboards', to='check_list.dashboard')),
            ],
        ),
    ]

# Generated manually for unified compliance update

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0186_intermediary_updates'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AssignmentBatch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('is_published', models.BooleanField(default=False, verbose_name='published')),
                ('event_id', models.CharField(max_length=255, unique=True)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('DISPATCHED', 'Dispatched')], default='OPEN', max_length=20)),
                ('window_expires_at', models.DateTimeField()),
                ('dispatched_at', models.DateTimeField(blank=True, null=True)),
                ('spoc_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_batches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['spoc_user', 'status'], name='core_assign_spoc_us_bd2181_idx'),
                    models.Index(fields=['status', 'window_expires_at'], name='core_assign_status_6f8dc5_idx'),
                ],
            },
        ),
        migrations.AddField(
            model_name='controlassignment',
            name='escalation_level',
            field=models.CharField(default='ASSIGNED', max_length=30),
        ),
        migrations.AddField(
            model_name='controlassignment',
            name='l1_reminder_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='controlassignment',
            name='l2_grace_deadline',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='controlassignment',
            name='l3_final_deadline',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='AssignmentBatchItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('is_published', models.BooleanField(default=False, verbose_name='published')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='core.assignmentbatch')),
                ('control_assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batch_items', to='core.controlassignment')),
            ],
            options={
                'unique_together': {('batch', 'control_assignment')},
            },
        ),
    ]

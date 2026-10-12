from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0185_create_missing_m2m_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='intermediarypartnerreport',
            name='is_active',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.CreateModel(
            name='IntermediaryGeneratedReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_published', models.BooleanField(default=True)),
                ('title', models.CharField(max_length=255)),
                ('scope_type', models.CharField(max_length=20)),
                ('scope_name', models.CharField(max_length=255)),
                ('scope_id', models.CharField(blank=True, default='', max_length=100)),
                ('reporting_period', models.CharField(blank=True, default='', max_length=255)),
                ('metrics_snapshot', models.JSONField(blank=True, default=dict)),
                ('file', models.FileField(blank=True, null=True, upload_to='intermediary_reports/')),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_compliance_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

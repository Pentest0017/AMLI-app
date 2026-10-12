import django.db.models.deletion
import iam.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0187_assignmentbatch_assignmentbatchitem_and_more'),
        ('iam', '0021_fix_auditee_iam_groups'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomReportTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('is_published', models.BooleanField(default=False, verbose_name='published')),
                ('report_type', models.CharField(help_text="Report type identifier: 'compliance' or 'intermediary_compliance'", max_length=50, unique=True)),
                ('title', models.CharField(default='Security Audit Compliance Report', max_length=255)),
                ('header_text', models.CharField(default='CONFIDENTIAL - FOR INTERNAL USE ONLY', max_length=255)),
                ('footer_text', models.CharField(default='Enterprise Compliance & Risk Management Platform', max_length=255)),
                ('company_name', models.CharField(default='Enterprise Compliance Organization', max_length=255)),
                ('primary_color', models.CharField(default='#4f46e5', max_length=20)),
                ('show_executive_summary', models.BooleanField(default=True)),
                ('show_findings', models.BooleanField(default=True)),
                ('show_evidence_details', models.BooleanField(default=True)),
                ('show_activity_history', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('folder', models.ForeignKey(default=iam.models.Folder.get_root_folder_id, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_folder', to='iam.folder')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]

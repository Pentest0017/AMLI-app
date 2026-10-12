from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def safe_add_reports_to_field(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('iam_user') AND name = 'reports_to_id')
            BEGIN
                ALTER TABLE iam_user ADD reports_to_id BIGINT NULL;
            END;
            """)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ('iam', '0027_user_department_user_designation'),
    ]

    operations = [
        migrations.RunPython(safe_add_reports_to_field, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='user',
                    name='reports_to',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='direct_reports',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Reports To',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

from django.db import migrations, models


def safe_mssql_migration(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
            -- legacy M2M table (pointing at core_qualification) must be replaced, not kept
            IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('ebios_rm_fearedevent_qualifications') AND name = 'qualification_id')
            BEGIN
                DROP TABLE ebios_rm_fearedevent_qualifications;
            END;
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ebios_rm_fearedevent_qualifications')
            BEGIN
                CREATE TABLE ebios_rm_fearedevent_qualifications (
                    id BIGINT IDENTITY(1,1) PRIMARY KEY,
                    fearedevent_id CHAR(32) NOT NULL,
                    terminology_id CHAR(32) NOT NULL
                );
            END;
            """)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0094_alter_incident_qualifications_and_more"),
        ("ebios_rm", "0015_replace_risk_origin"),
    ]

    operations = [
        migrations.RunPython(safe_mssql_migration, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="fearedevent",
                    name="qualifications",
                ),
                migrations.AddField(
                    model_name="fearedevent",
                    name="qualifications",
                    field=models.ManyToManyField(
                        blank=True,
                        limit_choices_to={"field_path": "qualifications", "is_visible": True},
                        related_name="feared_events_qualifications",
                        to="core.terminology",
                        verbose_name="Qualifications",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

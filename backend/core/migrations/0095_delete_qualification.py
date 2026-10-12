from django.db import migrations


def safe_drop_qualification_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor in ("microsoft", "mssql"):
            cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'core_qualification')
            BEGIN
                DROP TABLE core_qualification;
            END;
            """)
        else:
            cursor.execute("DROP TABLE IF EXISTS core_qualification;")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0094_alter_incident_qualifications_and_more"),
        ("ebios_rm", "0016_alter_fearedevent_qualifications"),
        ("resilience", "0003_alter_escalationthreshold_qualifications"),
    ]

    operations = [
        migrations.RunPython(safe_drop_qualification_table, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name="Qualification",
                ),
            ],
            database_operations=[],
        ),
    ]

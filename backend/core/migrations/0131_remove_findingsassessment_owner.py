from django.db import migrations


def safe_drop_table(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'core_findingsassessment_owner')
            BEGIN
                DROP TABLE core_findingsassessment_owner;
            END;
            """)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0130_remove_organisationobjective_new_assigned_to_and_more"),
    ]

    operations = [
        migrations.RunPython(safe_drop_table, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="findingsassessment",
                    name="owner",
                ),
            ],
            database_operations=[],
        ),
    ]

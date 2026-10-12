from django.db import migrations

from core.mssql_utils import drop_column


def safe_mssql_rename(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            for table, col, new_col in [
                ("core_organisationobjective", "assigned_to_id", "new_assigned_to_id"),
                ("core_tasktemplate", "assigned_to_id", "new_assigned_to_id"),
                ("core_perimeter", "default_assignee_id", "new_default_assignee_id"),
                ("core_timelineentry", "author_id", "new_author_id"),
            ]:
                drop_column(cursor, table, col)
                cursor.execute(f"""
                IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{table}') AND name = '{new_col}')
                BEGIN
                    EXEC sp_rename '{table}.{new_col}', '{col}', 'COLUMN';
                END;
                """)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        (
            "core",
            "0129_data_backfill_organisationobjective_tasktemplete_databreach_processing_actor",
        ),
    ]

    operations = [
        migrations.RunPython(safe_mssql_rename, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="organisationobjective",
                    name="assigned_to",
                ),
                migrations.RemoveField(
                    model_name="tasktemplate",
                    name="assigned_to",
                ),
                migrations.RemoveField(
                    model_name="perimeter",
                    name="default_assignee",
                ),
                migrations.RemoveField(
                    model_name="timelineentry",
                    name="author",
                ),
                migrations.RenameField(
                    model_name="organisationobjective",
                    old_name="new_assigned_to",
                    new_name="assigned_to",
                ),
                migrations.RenameField(
                    model_name="tasktemplate",
                    old_name="new_assigned_to",
                    new_name="assigned_to",
                ),
                migrations.RenameField(
                    model_name="perimeter",
                    old_name="new_default_assignee",
                    new_name="default_assignee",
                ),
                migrations.RenameField(
                    model_name="timelineentry",
                    old_name="new_author",
                    new_name="author",
                ),
            ],
            database_operations=[],
        ),
    ]

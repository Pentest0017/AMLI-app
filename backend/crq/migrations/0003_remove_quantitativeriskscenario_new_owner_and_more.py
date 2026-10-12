from django.db import migrations, models

from core.mssql_utils import drop_column


def safe_mssql_rename(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            drop_column(cursor, "crq_quantitativeriskscenario", "owner_id")
            cursor.execute("""
            IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('crq_quantitativeriskscenario') AND name = 'new_owner_id')
            BEGIN
                EXEC sp_rename 'crq_quantitativeriskscenario.new_owner_id', 'owner_id', 'COLUMN';
            END;
            """)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0127_remove_appliedcontrol_new_owner_and_more"),
        ("crq", "0002_fix_folder_inheritance"),
        ("crq", "0002_quantitativeriskscenario_new_owner_and_more"),
    ]

    operations = [
        migrations.RunPython(safe_mssql_rename, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="quantitativeriskscenario",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="quantitativeriskstudy",
                    name="authors",
                ),
                migrations.RemoveField(
                    model_name="quantitativeriskstudy",
                    name="reviewers",
                ),
                migrations.RenameField(
                    model_name="quantitativeriskscenario",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="quantitativeriskstudy",
                    old_name="new_authors",
                    new_name="authors",
                ),
                migrations.RenameField(
                    model_name="quantitativeriskstudy",
                    old_name="new_reviewers",
                    new_name="reviewers",
                ),
                migrations.AlterField(
                    model_name="quantitativeriskstudy",
                    name="authors",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="quantitative_risk_study_authors",
                        to="core.actor",
                        verbose_name="Authors",
                    ),
                ),
                migrations.AlterField(
                    model_name="quantitativeriskstudy",
                    name="reviewers",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="quantitative_risk_study_reviewers",
                        to="core.actor",
                        verbose_name="Reviewers",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

from django.db import migrations, models

from core.mssql_utils import drop_column


def safe_mssql_rename(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            # Drop legacy FK columns if present
            for table, col in [
                ("core_appliedcontrol", "owner_id"),
                ("core_asset", "owner_id"),
                ("core_evidence", "owner_id"),
                ("core_finding", "owner_id"),
                ("core_findingsassessment", "owner_id"),
                ("core_riskscenario", "owner_id"),
            ]:
                drop_column(cursor, table, col)
            # Rename FK columns new_owner_id -> owner_id
            for table in ["core_appliedcontrol", "core_asset", "core_evidence", "core_finding", "core_findingsassessment", "core_riskscenario"]:
                cursor.execute(f"""
                IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{table}') AND name = 'new_owner_id')
                BEGIN
                    EXEC sp_rename '{table}.new_owner_id', 'owner_id', 'COLUMN';
                END;
                """)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0126_data_backfill_actors"),
    ]

    operations = [
        migrations.RunPython(safe_mssql_rename, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="appliedcontrol",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="asset",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="complianceassessment",
                    name="authors",
                ),
                migrations.RemoveField(
                    model_name="complianceassessment",
                    name="reviewers",
                ),
                migrations.RemoveField(
                    model_name="evidence",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="finding",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="findingsassessment",
                    name="authors",
                ),
                migrations.RemoveField(
                    model_name="findingsassessment",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="findingsassessment",
                    name="reviewers",
                ),
                migrations.RemoveField(
                    model_name="incident",
                    name="owners",
                ),
                migrations.RemoveField(
                    model_name="riskassessment",
                    name="authors",
                ),
                migrations.RemoveField(
                    model_name="riskassessment",
                    name="reviewers",
                ),
                migrations.RemoveField(
                    model_name="riskscenario",
                    name="owner",
                ),
                migrations.RemoveField(
                    model_name="securityexception",
                    name="owners",
                ),
                migrations.RenameField(
                    model_name="appliedcontrol",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="asset",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="complianceassessment",
                    old_name="new_authors",
                    new_name="authors",
                ),
                migrations.RenameField(
                    model_name="complianceassessment",
                    old_name="new_reviewers",
                    new_name="reviewers",
                ),
                migrations.RenameField(
                    model_name="evidence",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="finding",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="findingsassessment",
                    old_name="new_authors",
                    new_name="authors",
                ),
                migrations.RenameField(
                    model_name="findingsassessment",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="findingsassessment",
                    old_name="new_reviewers",
                    new_name="reviewers",
                ),
                migrations.RenameField(
                    model_name="incident",
                    old_name="new_owners",
                    new_name="owners",
                ),
                migrations.RenameField(
                    model_name="riskassessment",
                    old_name="new_authors",
                    new_name="authors",
                ),
                migrations.RenameField(
                    model_name="riskassessment",
                    old_name="new_reviewers",
                    new_name="reviewers",
                ),
                migrations.RenameField(
                    model_name="riskscenario",
                    old_name="new_owner",
                    new_name="owner",
                ),
                migrations.RenameField(
                    model_name="securityexception",
                    old_name="new_owners",
                    new_name="owners",
                ),
                migrations.AlterField(
                    model_name="complianceassessment",
                    name="authors",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_authors",
                        to="core.actor",
                        verbose_name="Authors",
                    ),
                ),
                migrations.AlterField(
                    model_name="complianceassessment",
                    name="reviewers",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_reviewers",
                        to="core.actor",
                        verbose_name="Reviewers",
                    ),
                ),
                migrations.AlterField(
                    model_name="findingsassessment",
                    name="authors",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_authors",
                        to="core.actor",
                        verbose_name="Authors",
                    ),
                ),
                migrations.AlterField(
                    model_name="findingsassessment",
                    name="reviewers",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_reviewers",
                        to="core.actor",
                        verbose_name="Reviewers",
                    ),
                ),
                migrations.AlterField(
                    model_name="riskassessment",
                    name="authors",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_authors",
                        to="core.actor",
                        verbose_name="Authors",
                    ),
                ),
                migrations.AlterField(
                    model_name="riskassessment",
                    name="reviewers",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_reviewers",
                        to="core.actor",
                        verbose_name="Reviewers",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models

from core.mssql_utils import drop_column


def forward(apps, schema_editor):
    from privacy.terminology_seeds import (
        DEFAULT_PROCESSING_NATURES,
        DEFAULT_PERSONAL_DATA_CATEGORIES,
    )

    Terminology = apps.get_model("core", "Terminology")
    def seed(items):
        for item in items:
            Terminology.objects.update_or_create(
                name=item["name"],
                field_path=item["field_path"],
                defaults={k: v for k, v in item.items() if k != "is_visible"},
                create_defaults=item,
            )

    seed(DEFAULT_PROCESSING_NATURES)
    seed(DEFAULT_PERSONAL_DATA_CATEGORIES)


def safe_mssql_migration(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
            -- legacy M2M table (pointing at privacy_processingnature) must be replaced, not kept
            IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('privacy_processing_nature') AND name = 'processingnature_id')
            BEGIN
                DROP TABLE privacy_processing_nature;
            END;
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'privacy_processing_nature')
            BEGIN
                CREATE TABLE privacy_processing_nature (
                    id BIGINT IDENTITY(1,1) PRIMARY KEY,
                    processing_id BIGINT NOT NULL,
                    terminology_id BIGINT NOT NULL
                );
            END;
            IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('privacy_personaldata') AND name = 'category_id')
            BEGIN
                ALTER TABLE privacy_personaldata ADD category_id BIGINT NULL;
            END;
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'privacy_processingnature')
            BEGIN
                DROP TABLE privacy_processingnature;
            END;
            """)
            # Django only renames category -> category_old in its state (no DB operation), so the
            # real legacy column on SQL Server is still called "category".
            drop_column(cursor, "privacy_personaldata", "category_old")
            drop_column(cursor, "privacy_personaldata", "category")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("core", "0174_alter_terminology_field_path"),
        ("privacy", "0019_databreach_evidences"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
        migrations.RunPython(safe_mssql_migration, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="processing", old_name="nature", new_name="nature_old"
                ),
                migrations.AddField(
                    model_name="processing",
                    name="nature",
                    field=models.ManyToManyField(
                        blank=True,
                        limit_choices_to={
                            "field_path": "processing.nature",
                            "is_visible": True,
                        },
                        related_name="processing_natures",
                        to="core.terminology",
                    ),
                ),
                migrations.RenameField(
                    model_name="personaldata", old_name="category", new_name="category_old"
                ),
                migrations.AddField(
                    model_name="personaldata",
                    name="category",
                    field=models.ForeignKey(
                        null=True,
                        limit_choices_to={
                            "field_path": "personal_data.category",
                            "is_visible": True,
                        },
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="personal_data_categories",
                        to="core.terminology",
                    ),
                ),
                migrations.AlterField(
                    model_name="personaldata",
                    name="category",
                    field=models.ForeignKey(
                        limit_choices_to={
                            "field_path": "personal_data.category",
                            "is_visible": True,
                        },
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="personal_data_categories",
                        to="core.terminology",
                    ),
                ),
                migrations.RemoveField(model_name="processing", name="nature_old"),
                migrations.RemoveField(model_name="personaldata", name="category_old"),
                migrations.DeleteModel(name="ProcessingNature"),
            ],
            database_operations=[],
        ),
    ]

from django.db import migrations


def create_missing_tables(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'core_complianceassessment_reviewers')
            BEGIN
                CREATE TABLE core_complianceassessment_reviewers (
                    id BIGINT IDENTITY(1,1) PRIMARY KEY,
                    complianceassessment_id CHAR(32) NOT NULL,
                    actor_id CHAR(32) NOT NULL
                );
            END;
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'core_complianceassessment_authors')
            BEGIN
                CREATE TABLE core_complianceassessment_authors (
                    id BIGINT IDENTITY(1,1) PRIMARY KEY,
                    complianceassessment_id CHAR(32) NOT NULL,
                    actor_id CHAR(32) NOT NULL
                );
            END;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0184_indexes_and_constraints'),
    ]

    operations = [
        migrations.RunPython(create_missing_tables, reverse_code=migrations.RunPython.noop),
    ]

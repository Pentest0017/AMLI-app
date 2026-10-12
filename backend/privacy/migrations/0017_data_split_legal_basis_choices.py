# Generated manually for splitting legal basis choices

from django.db import migrations, models

from core.mssql_utils import drop_column


def safe_mssql_add_fields(apps, schema_editor):
    if schema_editor.connection.vendor in ("microsoft", "mssql"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('privacy_purpose') AND name = 'article_9_condition')
            BEGIN
                ALTER TABLE privacy_purpose ADD article_9_condition NVARCHAR(255) NULL;
            END;
            IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('privacy_datatransfer') AND name = 'transfer_mechanism')
            BEGIN
                ALTER TABLE privacy_datatransfer ADD transfer_mechanism NVARCHAR(255) NOT NULL DEFAULT '';
            END;
            """)
            drop_column(cursor, "privacy_datatransfer", "legal_basis")


def migrate_legal_basis_data(apps, schema_editor):
    Purpose = apps.get_model("privacy", "Purpose")
    DataTransfer = apps.get_model("privacy", "DataTransfer")

    art9_values = {
        "privacy_explicit_consent",
        "privacy_employment_social_security",
        "privacy_vital_interests_incapacity",
        "privacy_nonprofit_organization",
        "privacy_public_data",
        "privacy_legal_claims",
        "privacy_substantial_public_interest",
        "privacy_preventive_medicine",
        "privacy_public_health",
        "privacy_archiving_research",
    }

    combined_mappings = {
        "privacy_consent_and_contract": ("privacy_consent", None),
        "privacy_contract_and_legitimate_interests": ("privacy_contract", None),
        "privacy_child_consent": ("privacy_consent", None),
        "privacy_not_applicable": ("privacy_consent", None),
        "privacy_other": ("privacy_consent", None),
    }

    transfer_mappings = {
        "privacy_data_transfer_adequacy": "privacy_adequacy_decision",
        "privacy_data_transfer_safeguards": "privacy_appropriate_safeguards",
        "privacy_data_transfer_binding_rules": "privacy_binding_corporate_rules",
        "privacy_data_transfer_derogation": "privacy_derogation",
    }

    for purpose in Purpose.objects.all():
        old_value = purpose.legal_basis

        if old_value in art9_values:
            purpose.article_9_condition = old_value
            purpose.legal_basis = "privacy_consent"
            purpose.save()
        elif old_value in combined_mappings:
            new_legal_basis, new_art9 = combined_mappings[old_value]
            purpose.legal_basis = new_legal_basis
            purpose.article_9_condition = new_art9
            purpose.save()
        elif old_value in transfer_mappings:
            purpose.legal_basis = "privacy_consent"
            purpose.save()

    for transfer in DataTransfer.objects.all():
        old_value = getattr(transfer, "legal_basis", "")

        if old_value in transfer_mappings:
            transfer.transfer_mechanism = transfer_mappings[old_value]
            transfer.save()
        elif old_value:
            transfer.transfer_mechanism = ""
            transfer.save()


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("privacy", "0016_alter_datacontractor_name_alter_datarecipient_name_and_more"),
    ]

    operations = [
        migrations.RunPython(safe_mssql_add_fields, reverse_code=migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="purpose",
                    name="article_9_condition",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            (
                                "privacy_explicit_consent",
                                "Explicit Consent for Special Categories",
                            ),
                            (
                                "privacy_employment_social_security",
                                "Employment and Social Security Law",
                            ),
                            (
                                "privacy_vital_interests_incapacity",
                                "Vital Interests (Subject Physically/Legally Incapable)",
                            ),
                            (
                                "privacy_nonprofit_organization",
                                "Processing by Nonprofit Organization",
                            ),
                            (
                                "privacy_public_data",
                                "Data Manifestly Made Public by the Data Subject",
                            ),
                            (
                                "privacy_legal_claims",
                                "Establishment, Exercise or Defense of Legal Claims",
                            ),
                            (
                                "privacy_substantial_public_interest",
                                "Substantial Public Interest",
                            ),
                            (
                                "privacy_preventive_medicine",
                                "Preventive or Occupational Medicine",
                            ),
                            ("privacy_public_health", "Public Health"),
                            (
                                "privacy_archiving_research",
                                "Archiving, Research or Statistical Purposes",
                            ),
                        ],
                        max_length=255,
                        null=True,
                    ),
                ),
                migrations.AddField(
                    model_name="datatransfer",
                    name="transfer_mechanism",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            ("privacy_adequacy_decision", "Adequacy Decision (Art. 45)"),
                            (
                                "privacy_appropriate_safeguards",
                                "Appropriate Safeguards (Art. 46)",
                            ),
                            (
                                "privacy_binding_corporate_rules",
                                "Binding Corporate Rules (Art. 47)",
                            ),
                            (
                                "privacy_derogation",
                                "Derogation for Specific Situations (Art. 49)",
                            ),
                        ],
                        max_length=255,
                    ),
                ),
                migrations.RunPython(migrate_legal_basis_data, migrations.RunPython.noop),
                migrations.AlterField(
                    model_name="purpose",
                    name="legal_basis",
                    field=models.CharField(
                        choices=[
                            ("privacy_consent", "Consent"),
                            ("privacy_contract", "Performance of a Contract"),
                            ("privacy_legal_obligation", "Compliance with a Legal Obligation"),
                            ("privacy_vital_interests", "Protection of Vital Interests"),
                            (
                                "privacy_public_interest",
                                "Performance of a Task in the Public Interest",
                            ),
                            ("privacy_legitimate_interests", "Legitimate Interests"),
                        ],
                        default="privacy_consent",
                        max_length=255,
                    ),
                ),
                migrations.RemoveField(
                    model_name="datatransfer",
                    name="legal_basis",
                ),
            ],
            database_operations=[],
        ),
    ]

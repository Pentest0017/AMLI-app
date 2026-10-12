import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0180_alter_complianceassessment_audit_period_year"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IntermediaryFolder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "folder_type",
                    models.CharField(
                        choices=[("ROOT", "Root Repository"), ("YEAR", "Year"), ("DOMAIN", "Domain"), ("PARTNER", "Partner")],
                        default="YEAR",
                        max_length=20,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="core.intermediaryfolder",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="IntermediaryDomainAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                (
                    "domain_folder",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="core.intermediaryfolder",
                    ),
                ),
                ("approving_admins", models.ManyToManyField(blank=True, related_name="approving_admin_domain_assignments", to=settings.AUTH_USER_MODEL)),
                ("spoc_users", models.ManyToManyField(blank=True, related_name="spoc_domain_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="IntermediaryPartnerReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("title", models.CharField(max_length=255)),
                ("file_path", models.CharField(blank=True, default="", max_length=512)),
                (
                    "compliance_status",
                    models.CharField(
                        choices=[("COMPLIANT", "Compliant"), ("NON_COMPLIANT", "Not Compliant")],
                        default="COMPLIANT",
                        max_length=20,
                    ),
                ),
                (
                    "approval_status",
                    models.CharField(
                        choices=[("PENDING_APPROVAL", "Pending Approval"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")],
                        default="PENDING_APPROVAL",
                        max_length=20,
                    ),
                ),
                ("reviewer_feedback", models.TextField(blank=True, default="")),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_partner_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "partner_folder",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="core.intermediaryfolder",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_partner_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]

# Generated manually for Control Assignment, Evidence Management, Notification & Escalation

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0181_intermediary_compliance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Update ComplianceAssessment fields
        migrations.AddField(
            model_name="complianceassessment",
            name="audit_end_date",
            field=models.DateField(blank=True, null=True, verbose_name="Audit end date"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="audit_phase",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("EVIDENCE_COLLECTION", "Evidence Collection"),
                    ("UNDER_REVIEW", "Under Review"),
                    ("AUDIT_IN_PROGRESS", "Audit In Progress"),
                    ("CLOSED", "Closed"),
                    ("ARCHIVED", "Archived"),
                ],
                db_index=True,
                default="DRAFT",
                max_length=30,
                verbose_name="Audit phase",
            ),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="active_snapshot_version",
            field=models.IntegerField(default=1, verbose_name="Active snapshot version"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="completed_snapshot_version",
            field=models.IntegerField(blank=True, null=True, verbose_name="Completed snapshot version"),
        ),

        # 2. ControlAssignment
        migrations.CreateModel(
            name="ControlAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_control_assignments", to=settings.AUTH_USER_MODEL)),
                ("framework", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="control_assignments", to="core.framework")),
                ("requirement_node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="control_assignments", to="core.requirementnode")),
                ("reviewer_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewer_control_assignments", to=settings.AUTH_USER_MODEL)),
                ("spoc_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="spoc_control_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("requirement_node", "framework")},
            },
        ),

        # 3. EvidenceRequirement
        migrations.CreateModel(
            name="EvidenceRequirement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("is_mandatory", models.BooleanField(default=True)),
                ("order", models.IntegerField(default=0)),
                ("control_assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_requirements", to="core.controlassignment")),
            ],
        ),

        # 4. ControlEvidenceMapping
        migrations.CreateModel(
            name="ControlEvidenceMapping",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("control_assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_mappings", to="core.controlassignment")),
                ("evidence", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="control_mappings", to="core.evidence")),
                ("evidence_requirement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="evidence_mappings", to="core.evidencerequirement")),
                ("mapped_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mapped_evidences", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("control_assignment", "evidence_requirement", "evidence")},
            },
        ),

        # 5. AssessmentControlSnapshot
        migrations.CreateModel(
            name="AssessmentControlSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("snapshot_version", models.IntegerField(default=1)),
                ("compliance_assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="control_snapshots", to="core.complianceassessment")),
                ("control_assignment", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_snapshots", to="core.controlassignment")),
                ("framework", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_snapshots", to="core.framework")),
                ("requirement_node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_snapshots", to="core.requirementnode")),
                ("spoc_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="snapshot_spoc_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("compliance_assessment", "requirement_node", "snapshot_version")},
            },
        ),

        # 6. EvidenceRequirementSnapshot
        migrations.CreateModel(
            name="EvidenceRequirementSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("is_mandatory", models.BooleanField(default=True)),
                ("order", models.IntegerField(default=0)),
                ("assessment_control", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirement_snapshots", to="core.assessmentcontrolsnapshot")),
                ("source_requirement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="snapshots", to="core.evidencerequirement")),
            ],
        ),

        # 7. AssessmentReviewLevel
        migrations.CreateModel(
            name="AssessmentReviewLevel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("level", models.IntegerField(default=1)),
                ("order", models.IntegerField(default=0)),
                ("assessment_control", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_levels", to="core.assessmentcontrolsnapshot")),
                ("reviewer_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessment_review_levels", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("assessment_control", "reviewer_user", "level")},
            },
        ),

        # 8. AuditEvidenceLink
        migrations.CreateModel(
            name="AuditEvidenceLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("review_status", models.CharField(choices=[("PENDING_REVIEW", "Pending Review"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING_REVIEW", max_length=20)),
                ("review_level", models.IntegerField(default=1)),
                ("reviewer_feedback", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.IntegerField(default=1)),
                ("expiry_warning", models.BooleanField(default=False)),
                ("superseded_reason", models.CharField(blank=True, choices=[("", ""), ("NEW_REVISION", "Superseded by newer revision"), ("RESUBMISSION", "Superseded by re-upload after rejection")], default="", max_length=20)),
                ("assessment_control", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_links", to="core.assessmentcontrolsnapshot")),
                ("control_evidence_mapping", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_links", to="core.controlevidencemapping")),
                ("evidence", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_links", to="core.evidence")),
                ("evidence_requirement_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="evidence_links", to="core.evidencerequirementsnapshot")),
                ("evidence_revision", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_links", to="core.evidencerevision")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_audit_evidences", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("assessment_control", "evidence_revision", "review_level")},
            },
        ),

        # 9. AssignmentChangeLog
        migrations.CreateModel(
            name="AssignmentChangeLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("action_type", models.CharField(choices=[("CREATED", "Assignment Created"), ("MODIFIED", "Assignment Modified"), ("DEACTIVATED", "Assignment Deactivated"), ("REACTIVATED", "Assignment Reactivated"), ("BULK_ASSIGNED", "Bulk Assignment")], max_length=20)),
                ("field_changed", models.CharField(blank=True, default="", max_length=50)),
                ("reason", models.TextField(blank=True, default="")),
                ("bulk_operation_id", models.UUIDField(blank=True, null=True)),
                ("changed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assignment_changes_made", to=settings.AUTH_USER_MODEL)),
                ("control_assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="change_logs", to="core.controlassignment")),
                ("new_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assignment_changes_to", to=settings.AUTH_USER_MODEL)),
                ("previous_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assignment_changes_from", to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # 10. AuditCompletion
        migrations.CreateModel(
            name="AuditCompletion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("completion_number", models.IntegerField()),
                ("snapshot_version", models.IntegerField()),
                ("closed_at", models.DateTimeField(auto_now_add=True)),
                ("summary_snapshot", models.JSONField(default=dict)),
                ("notes", models.TextField(blank=True, default="")),
                ("closed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_closures", to=settings.AUTH_USER_MODEL)),
                ("compliance_assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="completions", to="core.complianceassessment")),
            ],
            options={
                "unique_together": {("compliance_assessment", "completion_number")},
            },
        ),

        # 11. AuditReopenLog
        migrations.CreateModel(
            name="AuditReopenLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("reopened_at", models.DateTimeField(auto_now_add=True)),
                ("previous_phase", models.CharField(max_length=30)),
                ("previous_snapshot_version", models.IntegerField()),
                ("new_snapshot_version", models.IntegerField()),
                ("reopen_reason", models.TextField()),
                ("compliance_assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reopen_logs", to="core.complianceassessment")),
                ("reopened_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_reopens", to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # 12. Notification
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("notification_type", models.CharField(choices=[("ASSIGNMENT", "New Control Assignment"), ("EVIDENCE_DUE", "Evidence Due Soon"), ("EVIDENCE_SUBMITTED", "Evidence Submitted for Review"), ("EVIDENCE_APPROVED", "Evidence Approved"), ("EVIDENCE_REJECTED", "Evidence Rejected"), ("ESCALATION", "Escalation Alert"), ("AUDIT_PHASE_CHANGE", "Audit Phase Changed"), ("INTERMEDIARY", "Intermediary Compliance"), ("GENERAL", "General")], default="GENERAL", max_length=30)),
                ("link_url", models.CharField(blank=True, default="", max_length=512)),
                ("is_read", models.BooleanField(default=False)),
                ("is_archived", models.BooleanField(db_index=True, default=False)),
                ("send_email", models.BooleanField(default=False)),
                ("email_sent", models.BooleanField(default=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # 13. EscalationRule
        migrations.CreateModel(
            name="EscalationRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("escalation_steps", models.JSONField(default=list)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_escalation_rules", to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # 14. EscalationLog
        migrations.CreateModel(
            name="EscalationLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_published", models.BooleanField(default=True)),
                ("trigger_type", models.CharField(choices=[("AUTOMATIC", "Automatic (Scheduled)"), ("MANUAL", "Manual (Button Click)")], max_length=20)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("email_sent", models.BooleanField(default=False)),
                ("step_label", models.CharField(max_length=100)),
                ("escalation_date", models.DateField()),
                ("compliance_assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="escalation_logs", to="core.complianceassessment")),
                ("control_assignment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="escalation_logs", to="core.controlassignment")),
                ("escalation_rule", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="logs", to="core.escalationrule")),
                ("recipient_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="received_escalations", to=settings.AUTH_USER_MODEL)),
                ("triggered_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggered_escalations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("compliance_assessment", "control_assignment", "escalation_rule", "step_label", "escalation_date")},
            },
        ),
    ]

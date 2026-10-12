from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from core.models import (
    ComplianceAssessment,
    ControlAssignment,
    AssessmentControlSnapshot,
    EvidenceRequirementSnapshot,
    AssessmentReviewLevel,
    AuditEvidenceLink,
    ControlEvidenceMapping,
    AuditCompletion,
    AuditReopenLog,
)
from core.expiry_service import ExpiryService


VALID_TRANSITIONS = {
    "DRAFT": ["EVIDENCE_COLLECTION"],
    "EVIDENCE_COLLECTION": ["UNDER_REVIEW", "DRAFT"],
    "UNDER_REVIEW": ["AUDIT_IN_PROGRESS", "EVIDENCE_COLLECTION"],
    "AUDIT_IN_PROGRESS": ["CLOSED"],
    "CLOSED": ["ARCHIVED", "EVIDENCE_COLLECTION"],
    "ARCHIVED": [],
}


def transition_audit_phase(assessment_id, new_phase: str, user, reopen_reason: str = ""):
    """
    Executes audit phase transition under transaction.atomic() with pessimistic locking.
    """
    with transaction.atomic():
        assessment = (
            ComplianceAssessment.objects
            .select_for_update()
            .get(id=assessment_id)
        )

        current_phase = assessment.audit_phase
        if new_phase not in VALID_TRANSITIONS.get(current_phase, []):
            raise ValidationError(
                f"Cannot transition audit phase from '{current_phase}' to '{new_phase}'."
            )

        # Idempotency check for CLOSED phase
        if current_phase == "CLOSED" and new_phase == "CLOSED":
            return AuditCompletion.objects.filter(compliance_assessment=assessment).order_by("-completion_number").first()

        # Handle transition DRAFT -> EVIDENCE_COLLECTION (initial snapshot creation)
        if current_phase == "DRAFT" and new_phase == "EVIDENCE_COLLECTION":
            create_snapshots(assessment, version=1)
            auto_populate_evidence(assessment)

        # Handle transition CLOSED -> EVIDENCE_COLLECTION (reopen)
        elif current_phase == "CLOSED" and new_phase == "EVIDENCE_COLLECTION":
            if not reopen_reason or not reopen_reason.strip():
                raise ValidationError("A non-empty reopen_reason is required to reopen a closed audit.")

            prev_version = assessment.active_snapshot_version
            new_version = prev_version + 1
            assessment.active_snapshot_version = new_version

            AuditReopenLog.objects.create(
                compliance_assessment=assessment,
                reopened_by=user,
                previous_phase=current_phase,
                previous_snapshot_version=prev_version,
                new_snapshot_version=new_version,
                reopen_reason=reopen_reason.strip(),
            )

            create_snapshots(assessment, version=new_version)
            auto_populate_evidence(assessment)

        # Handle transition AUDIT_IN_PROGRESS -> CLOSED (completion recording)
        elif new_phase == "CLOSED":
            assessment.completed_snapshot_version = assessment.active_snapshot_version
            completion_num = AuditCompletion.objects.filter(compliance_assessment=assessment).count() + 1
            
            # Aggregate summary snapshot metrics
            snapshots = assessment.control_snapshots.filter(
                snapshot_version=assessment.active_snapshot_version, is_active=True
            )
            total = snapshots.count()
            approved_links = AuditEvidenceLink.objects.filter(
                assessment_control__in=snapshots, review_status="APPROVED", is_active=True
            ).count()

            summary = {
                "total_controls": total,
                "approved_evidences": approved_links,
                "completed_snapshot_version": assessment.completed_snapshot_version,
            }

            AuditCompletion.objects.get_or_create(
                compliance_assessment=assessment,
                completion_number=completion_num,
                defaults={
                    "snapshot_version": assessment.active_snapshot_version,
                    "closed_by": user,
                    "summary_snapshot": summary,
                }
            )

        assessment.audit_phase = new_phase
        assessment.save(update_fields=["audit_phase", "active_snapshot_version", "completed_snapshot_version"])

        # Trigger notification for phase change
        from core.notification_service import NotificationService
        NotificationService.notify_audit_phase_change(assessment, current_phase, new_phase)

        return assessment


def create_snapshots(assessment, version: int = 1):
    """
    Freezes ControlAssignment state for assessment into AssessmentControlSnapshot records.
    Works for both Full Framework Scope and Custom Scope assessments.
    """
    with transaction.atomic():
        # Ensure requirement assessments exist for the compliance assessment
        if assessment.requirement_assessments.count() == 0:
            try:
                assessment.create_requirement_assessments()
            except Exception as e:
                print(f"create_requirement_assessments warning: {e}")

        req_node_ids = list(
            assessment.requirement_assessments.values_list("requirement_id", flat=True)
        )
        if not req_node_ids and assessment.framework:
            assignments = ControlAssignment.objects.filter(framework=assessment.framework, is_active=True)
        else:
            assignments = ControlAssignment.objects.filter(requirement_node_id__in=req_node_ids, is_active=True)

        assignments = (
            assignments.select_for_update()
            .select_related("requirement_node", "spoc_user", "reviewer_user")
            .prefetch_related("evidence_requirements")
        )

        for ca in assignments:
            snapshot, created = AssessmentControlSnapshot.objects.get_or_create(
                compliance_assessment=assessment,
                requirement_node=ca.requirement_node,
                snapshot_version=version,
                defaults={
                    "control_assignment": ca,
                    "framework": ca.framework,
                    "spoc_user": ca.spoc_user,
                }
            )

            # Copy evidence requirements into normalized snapshot table
            reqs = ca.evidence_requirements.filter(is_active=True)
            for req in reqs:
                EvidenceRequirementSnapshot.objects.get_or_create(
                    assessment_control=snapshot,
                    source_requirement=req,
                    defaults={
                        "name": req.name,
                        "description": req.description,
                        "is_mandatory": req.is_mandatory,
                        "order": req.order,
                    }
                )

            # Create primary reviewer level 1
            if ca.reviewer_user:
                AssessmentReviewLevel.objects.get_or_create(
                    assessment_control=snapshot,
                    reviewer_user=ca.reviewer_user,
                    level=1,
                    defaults={"order": 0}
                )


def auto_populate_evidence(assessment):
    """
    Populates global ControlEvidenceMappings into AuditEvidenceLinks for active_snapshot_version.
    Enforces 100% Audit-Driven Evidence Collection Rules:
    - If NO evidence exists OR evidence is ALREADY EXPIRED (expiry_date < today) OR evidence EXPIRES BEFORE AUDIT END DATE (expiry_date < audit_end_date):
      -> Request evidence resubmission (review_status="PENDING_REVIEW", expiry_warning=True).
    - If evidence is VALID THROUGH AUDIT END DATE (expiry_date >= audit_end_date OR expiry_date is None):
      -> Attach existing evidence link as APPROVED / valid without prompting SPOC for re-upload.
    """
    active_version = assessment.active_snapshot_version
    snapshots = assessment.control_snapshots.filter(
        snapshot_version=active_version, is_active=True
    ).select_related("control_assignment")

    now_date = timezone.now().date()
    audit_end = assessment.audit_end_date or assessment.due_date

    for snapshot in snapshots:
        if not snapshot.control_assignment:
            continue

        mappings = ControlEvidenceMapping.objects.filter(
            control_assignment=snapshot.control_assignment, is_active=True
        ).select_related("evidence", "evidence_requirement")

        for mapping in mappings:
            latest_revision = mapping.evidence.revisions.order_by("-version").first()
            if not latest_revision:
                continue

            # Deterministic requirement matching (OS-4)
            matched_req_snapshot = map_requirement_snapshot(snapshot, mapping.evidence_requirement)

            ev_expiry = mapping.evidence.expiry_date
            is_expired = (ev_expiry is not None) and (ev_expiry < now_date)
            expires_before_end = (ev_expiry is not None) and (audit_end is not None) and (ev_expiry < audit_end)

            needs_resubmission = is_expired or expires_before_end
            status = "PENDING_REVIEW" if needs_resubmission else "APPROVED"

            link, created = AuditEvidenceLink.objects.get_or_create(
                assessment_control=snapshot,
                evidence_revision=latest_revision,
                review_level=1,
                defaults={
                    "control_evidence_mapping": mapping,
                    "evidence": mapping.evidence,
                    "evidence_requirement_snapshot": matched_req_snapshot,
                    "review_status": status,
                    "expiry_warning": needs_resubmission,
                    "is_active": True,
                }
            )
            if not created:
                link.review_status = status
                link.expiry_warning = needs_resubmission
                link.save(update_fields=["review_status", "expiry_warning"])


def map_requirement_snapshot(snapshot, source_req):
    """
    Deterministic requirement matching (OS-4 / v5.1).
    Lowest order first, then earliest created_at.
    """
    if not source_req:
        return snapshot.requirement_snapshots.order_by("order", "created_at").first()

    match = snapshot.requirement_snapshots.filter(name=source_req.name).order_by("order", "created_at").first()
    if match:
        return match

    return snapshot.requirement_snapshots.order_by("order", "created_at").first()


def get_active_evidence_link(assignment, requirement=None):
    """
    Authoritative single-source-of-truth resolver for active evidence link.
    1. Look for an active requirement-specific link.
    2. Fall back to an active assignment-level link.
    3. Never select an inactive (is_active=False) historical link.
    """
    if not assignment:
        return None

    from django.db.models import Q
    from core.models import AuditEvidenceLink

    if requirement:
        link = AuditEvidenceLink.objects.filter(
            Q(control_evidence_mapping__control_assignment=assignment) | Q(assessment_control__control_assignment=assignment),
            Q(control_evidence_mapping__evidence_requirement=requirement) | Q(evidence_requirement_snapshot__source_requirement=requirement),
            is_active=True,
        ).order_by("-created_at").first()
        if link:
            return link

    return AuditEvidenceLink.objects.filter(
        Q(control_evidence_mapping__control_assignment=assignment) | Q(assessment_control__control_assignment=assignment),
        is_active=True,
    ).order_by("-created_at").first()


def calculate_overall_control_status(assessment_control_snapshot):
    """
    Evaluates overall control status from AuditEvidenceLinks across all review levels (OS-5).
    """
    links = assessment_control_snapshot.evidence_links.filter(is_active=True)

    # 1. Any rejection at any level -> REJECTED
    if links.filter(review_status="REJECTED").exists():
        return "REJECTED"

    # 2. Check mandatory requirements
    mandatory_req_ids = set(
        assessment_control_snapshot.requirement_snapshots
        .filter(is_mandatory=True)
        .values_list("id", flat=True)
    )

    approved_req_ids = set(
        links.filter(review_status="APPROVED")
        .values_list("evidence_requirement_snapshot_id", flat=True)
    )

    # All mandatory requirements have at least one approved link -> APPROVED
    if mandatory_req_ids and mandatory_req_ids.issubset(approved_req_ids):
        return "APPROVED"

    # If no mandatory requirements defined but has approved link -> APPROVED
    if not mandatory_req_ids and links.filter(review_status="APPROVED").exists():
        return "APPROVED"

    # Otherwise -> PENDING_REVIEW
    return "PENDING_REVIEW"


def shift_date_by_year(d, years=1):
    """Shifts a date forward by specified years safely handling leap years."""
    if not d:
        return None
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def shift_period_string_by_year(period_str, years=1):
    """
    Shifts 4-digit years in audit period string forward by specified years.
    e.g. 'June 1, 2024 - May 30, 2025' -> 'June 1, 2025 - May 30, 2026'
    e.g. '2024-2025' -> '2025-2026'
    """
    if not period_str:
        return period_str
    import re
    return re.sub(r"\b(19\d\d|20\d\d)\b", lambda m: str(int(m.group(1)) + years), str(period_str))


def trigger_next_yearly_assessment(assessment, years=1):
    """
    Triggers the next annual cycle for a scheduled audit, incrementing start_date,
    evidence_due_date, due_date / audit_end_date, and audit_period_year by +1 year.
    """
    new_audit_period = shift_period_string_by_year(assessment.audit_period_year, years)

    # Shift year in name if present, or append new_audit_period to ensure unique scope name
    new_name = shift_period_string_by_year(assessment.name, years)
    if new_name == assessment.name and new_audit_period:
        new_name = f"{assessment.name} ({new_audit_period})"

    new_asm = ComplianceAssessment.objects.create(
        name=new_name[:100],
        description=assessment.description,
        framework=assessment.framework,
        scope_mode=assessment.scope_mode,
        schedule_type=assessment.schedule_type,
        start_date=shift_date_by_year(assessment.start_date, years),
        evidence_due_date=shift_date_by_year(assessment.evidence_due_date, years),
        audit_end_date=shift_date_by_year(assessment.audit_end_date, years),
        due_date=shift_date_by_year(assessment.due_date, years),
        audit_period_year=new_audit_period,
        folder=assessment.folder,
        perimeter=assessment.perimeter,
        status="planned",
        audit_phase="DRAFT",
    )
    return new_asm



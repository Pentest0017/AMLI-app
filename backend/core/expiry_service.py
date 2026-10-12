import uuid
from django.db import models
from core.models import AuditEvidenceLink, ComplianceAssessment, Evidence


class ExpiryService:
    """
    Centralized expiry recalculation service.
    Pushes boolean condition updates directly into MySQL via SQL Case/When expressions.
    """

    @staticmethod
    def recalculate_for_evidence(evidence_id: uuid.UUID):
        """
        Recalculates expiry warnings for all active AuditEvidenceLinks referencing a specific Evidence.
        """
        evidence = Evidence.objects.filter(id=evidence_id).first()
        if not evidence:
            return

        links = AuditEvidenceLink.objects.filter(
            evidence_id=evidence_id, is_active=True
        ).select_related("assessment_control__compliance_assessment")

        updates = []
        for link in links:
            audit_end = link.assessment_control.compliance_assessment.audit_end_date
            new_warning = (
                evidence.expiry_date is not None
                and audit_end is not None
                and evidence.expiry_date < audit_end
            )
            if link.expiry_warning != new_warning:
                link.expiry_warning = new_warning
                updates.append(link)

        if updates:
            AuditEvidenceLink.objects.bulk_update(updates, ["expiry_warning"], batch_size=500)

    @staticmethod
    def recalculate_for_assessment(assessment_id: uuid.UUID):
        """
        Pushes boolean warning evaluation directly into SQL UPDATE for an assessment's links.
        """
        assessment = ComplianceAssessment.objects.filter(id=assessment_id).first()
        if not assessment or not assessment.audit_end_date:
            AuditEvidenceLink.objects.filter(
                assessment_control__compliance_assessment_id=assessment_id,
                is_active=True
            ).update(expiry_warning=False)
            return

        AuditEvidenceLink.objects.filter(
            assessment_control__compliance_assessment_id=assessment_id,
            is_active=True
        ).update(
            expiry_warning=models.Case(
                models.When(
                    evidence__expiry_date__isnull=False,
                    evidence__expiry_date__lt=assessment.audit_end_date,
                    then=True
                ),
                default=False,
                output_field=models.BooleanField()
            )
        )

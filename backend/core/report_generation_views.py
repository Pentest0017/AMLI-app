from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from core.models import ComplianceAssessment, AssessmentControlSnapshot, AuditEvidenceLink, AuditCompletion, Framework
from core.audit_lifecycle import calculate_overall_control_status


class ControlAssignmentReportSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lightweight summary metrics endpoint for report generation (BS-16).
        Queries completed_snapshot_version for closed audits, or active_snapshot_version for active audits.
        """
        assessment_id = request.query_params.get("assessment_id")
        framework_id = request.query_params.get("framework_id")
        completion_number = request.query_params.get("completion_number")

        assessment = None
        if assessment_id:
            assessment = ComplianceAssessment.objects.filter(id=assessment_id).first()

        if not assessment and framework_id:
            assessment = ComplianceAssessment.objects.filter(framework_id=framework_id).first()
            if not assessment:
                fw = Framework.objects.filter(id=framework_id).first()
                if fw:
                    assessment, _ = ComplianceAssessment.objects.get_or_create(
                        name=f"{fw.name} Audit Assessment",
                        framework=fw,
                        defaults={
                            "audit_period_year": 2026,
                            "audit_phase": "EVIDENCE_COLLECTION",
                            "created_by": request.user
                        }
                    )

        if not assessment:
            assessment = ComplianceAssessment.objects.first()

        if not assessment:
            return Response({
                "assessment_id": "",
                "assessment_name": "No Assessment",
                "audit_period_year": 2026,
                "audit_phase": "DRAFT",
                "summary": {
                    "total_controls": 0,
                    "controls_compliant": 0,
                    "controls_non_compliant": 0,
                    "controls_pending_review": 0,
                    "controls_missing_evidence": 0,
                    "compliance_percentage": 0.0,
                    "evidences_expiring_before_audit": 0,
                }
            })

        target_version = assessment.active_snapshot_version
        if completion_number:
            closure = AuditCompletion.objects.filter(compliance_assessment=assessment, completion_number=completion_number).first()
            if closure:
                target_version = closure.snapshot_version
        elif assessment.audit_phase in ["CLOSED", "ARCHIVED"] and assessment.completed_snapshot_version:
            target_version = assessment.completed_snapshot_version

        snapshots = AssessmentControlSnapshot.all_objects.filter(
            compliance_assessment=assessment,
            snapshot_version=target_version
        ).select_related("requirement_node", "framework", "spoc_user")

        total_controls = snapshots.count()
        compliant = 0
        non_compliant = 0
        pending_review = 0
        missing_evidence = 0
        assigned_count = 0
        unassigned_count = 0
        evidence_submitted = 0
        expiry_warnings_count = 0

        for snapshot in snapshots:
            overall = calculate_overall_control_status(snapshot)
            if overall == "APPROVED":
                compliant += 1
            elif overall == "REJECTED":
                non_compliant += 1
            elif overall == "PENDING_REVIEW":
                pending_review += 1

            if snapshot.spoc_user is not None or getattr(snapshot, 'reviewer_user', None) is not None:
                assigned_count += 1
            else:
                unassigned_count += 1

            if snapshot.evidence_links.filter(is_active=True).exists():
                evidence_submitted += 1
            else:
                missing_evidence += 1

            expiry_warnings_count += snapshot.evidence_links.filter(expiry_warning=True, is_active=True).count()

        compliance_pct = round((compliant / total_controls * 100), 1) if total_controls > 0 else 0.0

        return Response({
            "assessment_id": str(assessment.id),
            "assessment_name": assessment.name,
            "audit_period_year": assessment.audit_period_year,
            "audit_phase": assessment.audit_phase,
            "snapshot_version": target_version,
            "evidence_due_date": assessment.evidence_due_date.isoformat() if assessment.evidence_due_date else None,
            "audit_end_date": assessment.audit_end_date.isoformat() if assessment.audit_end_date else None,
            "total_controls": total_controls,
            "assigned_controls_count": assigned_count,
            "unassigned_controls_count": unassigned_count,
            "evidence_submitted_count": evidence_submitted,
            "pending_spoc_submission": missing_evidence,
            "pending_evidence_upload": missing_evidence,
            "controls_pending_review": pending_review,
            "approved_controls_count": compliant,
            "rejected_controls_count": non_compliant,
            "completion_percentage": compliance_pct,
            "summary": {
                "total_controls": total_controls,
                "assigned_controls_count": assigned_count,
                "unassigned_controls_count": unassigned_count,
                "evidence_submitted_count": evidence_submitted,
                "pending_spoc_submission": missing_evidence,
                "pending_evidence_upload": missing_evidence,
                "controls_pending_review": pending_review,
                "controls_compliant": compliant,
                "approved_controls_count": compliant,
                "controls_non_compliant": non_compliant,
                "rejected_controls_count": non_compliant,
                "compliance_percentage": compliance_pct,
                "completion_percentage": compliance_pct,
                "evidences_expiring_before_audit": expiry_warnings_count,
            }
        })


class ControlAssignmentReportControlsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Paginated control details endpoint for report generation (page_size=50).
        """
        assessment_id = request.query_params.get("assessment_id")
        framework_id = request.query_params.get("framework_id")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        assessment = None
        if assessment_id:
            assessment = ComplianceAssessment.objects.filter(id=assessment_id).first()

        if not assessment and framework_id:
            assessment = ComplianceAssessment.objects.filter(framework_id=framework_id).first()

        if not assessment:
            assessment = ComplianceAssessment.objects.first()

        if not assessment:
            return Response({"total": 0, "page": page, "page_size": page_size, "results": []})

        target_version = assessment.completed_snapshot_version if (assessment.audit_phase in ["CLOSED", "ARCHIVED"] and assessment.completed_snapshot_version) else assessment.active_snapshot_version

        snapshots_qs = AssessmentControlSnapshot.all_objects.filter(
            compliance_assessment=assessment,
            snapshot_version=target_version
        ).select_related("requirement_node", "framework", "spoc_user").order_by("requirement_node__order_id")

        total = snapshots_qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated_snapshots = snapshots_qs[start:end]

        controls_list = []
        for snapshot in paginated_snapshots:
            links = snapshot.evidence_links.filter(is_active=True).select_related("evidence", "reviewed_by")
            overall = calculate_overall_control_status(snapshot)

            evidence_items = []
            for l in links:
                evidence_items.append({
                    "id": str(l.id),
                    "name": l.evidence.name,
                    "review_status": l.review_status,
                    "reviewer_feedback": l.reviewer_feedback,
                    "expiry_warning": l.expiry_warning,
                    "reviewed_by": l.reviewed_by.email if l.reviewed_by else None,
                })

            controls_list.append({
                "snapshot_id": str(snapshot.id),
                "ref_id": snapshot.requirement_node.ref_id,
                "name": snapshot.requirement_node.name,
                "framework": snapshot.framework.name,
                "spoc": snapshot.spoc_user.email if snapshot.spoc_user else None,
                "overall_status": overall,
                "evidence_count": len(evidence_items),
                "evidences": evidence_items,
            })

        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": controls_list,
        })

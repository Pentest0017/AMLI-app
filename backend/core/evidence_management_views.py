# Updated: 2026-08-24T11:13:30
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from core.models import (
    ControlAssignment,
    ControlEvidenceMapping,
    AssessmentControlSnapshot,
    AuditEvidenceLink,
    Evidence,
    EvidenceRevision,
    ComplianceAssessment,
    EvidenceRequirementSnapshot,
    RequirementNode,
    RequirementAssessment,
    Framework,
)
from core.search_service import SearchService
from core.expiry_service import ExpiryService
from core.notification_service import NotificationService
from core.audit_lifecycle import map_requirement_snapshot


class EvidenceSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        SPOC evidence submission endpoint (manual or requirement-based).
        Creates global Evidence + EvidenceRevision + ControlEvidenceMapping + AuditEvidenceLink in active audits.
        """
        user = request.user
        control_assignment_id = request.data.get("control_assignment_id")
        requirement_id = request.data.get("evidence_requirement_id")
        title = request.data.get("title", "").strip()
        description = request.data.get("description", "")
        expiry_date = request.data.get("expiry_date")
        file_obj = request.FILES.get("file")

        if not control_assignment_id or not title or not file_obj:
            return Response({"error": "control_assignment_id, title, and file are required."}, status=status.HTTP_400_BAD_REQUEST)

        assignment = ControlAssignment.objects.filter(id=control_assignment_id, is_active=True).first()
        if not assignment:
            return Response({"error": "Control assignment not found."}, status=status.HTTP_404_NOT_FOUND)

        # Validate user is SPOC, Admin, Webadmin, or Superadmin
        role = getattr(user, "platform_role", "")
        is_spoc = (assignment.spoc_user == user) or (assignment.spoc_user and assignment.spoc_user.email.lower() == user.email.lower())
        is_admin_role = user.is_superuser or role in ["superadmin", "webadmin", "admin"]

        if not is_spoc and not is_admin_role:
            return Response({"error": "Only assigned SPOC, Admin, or Webadmin can submit evidence for this control."}, status=status.HTTP_403_FORBIDDEN)

        version_input = request.data.get("version", "1")
        try:
            version_val = int(str(version_input).split(".")[0])
        except (ValueError, TypeError):
            version_val = 1

        with transaction.atomic():
            # 1. Create global Evidence (reusing existing model) safely avoiding name collisions
            folder = assignment.framework.folder if hasattr(assignment.framework, "folder") else None
            evidence_name = title
            counter = 1
            while Evidence.objects.filter(name=evidence_name, folder=folder).exists():
                evidence_name = f"{title} ({counter})"
                counter += 1

            evidence = Evidence.objects.create(
                name=evidence_name,
                description=description,
                expiry_date=expiry_date if expiry_date else None,
                folder=folder,
                status="in_review",
            )
            # 2. Create EvidenceRevision (reusing existing model)
            revision = EvidenceRevision.objects.create(
                evidence=evidence,
                version=version_val,
                attachment=file_obj,
                observation=description,
            )

            # 3. Create ControlEvidenceMapping
            mapping = ControlEvidenceMapping.objects.create(
                control_assignment=assignment,
                evidence_requirement_id=requirement_id if requirement_id else None,
                evidence=evidence,
                mapped_by=user,
            )

            # 4. Deactivate ALL previous active evidence links for THIS control assignment so new upload takes precedence
            AuditEvidenceLink.objects.filter(
                Q(control_evidence_mapping__control_assignment=assignment) | Q(assessment_control__control_assignment=assignment),
                is_active=True
            ).update(is_active=False)

            # 5. Auto-populate active audit snapshots and create valid AuditEvidenceLink instances
            all_matching_audits = list(ComplianceAssessment.objects.filter(
                Q(framework=assignment.framework) | Q(framework=None)
            ).distinct())

            active_audits = []
            for audit in all_matching_audits:
                if audit and RequirementAssessment.objects.filter(compliance_assessment=audit, requirement=assignment.requirement_node).exists():
                    active_audits.append(audit)

            links_created = 0
            for audit in active_audits:
                if not audit:
                    continue
                try:
                    snapshot, _ = AssessmentControlSnapshot.objects.get_or_create(
                        compliance_assessment=audit,
                        control_assignment=assignment,
                        snapshot_version=getattr(audit, "active_snapshot_version", 1),
                        defaults={
                            "requirement_node": assignment.requirement_node,
                            "framework": assignment.framework,
                            "spoc_user": assignment.spoc_user,
                            "is_active": True
                        }
                    )

                    matched_req = None
                    if mapping.evidence_requirement:
                        matched_req = map_requirement_snapshot(snapshot, mapping.evidence_requirement)

                    expiry_warn = False
                    if evidence.expiry_date and audit.audit_end_date:
                        expiry_warn = evidence.expiry_date < audit.audit_end_date

                    AuditEvidenceLink.objects.create(
                        assessment_control=snapshot,
                        control_evidence_mapping=mapping,
                        evidence=evidence,
                        evidence_revision=revision,
                        evidence_requirement_snapshot=matched_req,
                        review_status="PENDING_REVIEW",
                        reviewer_feedback="",
                        review_level=1,
                        expiry_warning=expiry_warn,
                        is_active=True,
                    )
                    links_created += 1
                except Exception as ex:
                    import logging
                    logging.getLogger(__name__).error("Error creating AuditEvidenceLink snapshot link: %s", str(ex))

            if links_created == 0:
                fallback_snapshot = AssessmentControlSnapshot.objects.filter(
                    control_assignment=assignment, is_active=True
                ).first()
                if not fallback_snapshot:
                    audit = ComplianceAssessment.objects.filter(
                        Q(framework=assignment.framework) | Q(framework__isnull=True)
                    ).first() or ComplianceAssessment.objects.first()
                    if audit:
                        fallback_snapshot, _ = AssessmentControlSnapshot.objects.get_or_create(
                            compliance_assessment=audit,
                            control_assignment=assignment,
                            snapshot_version=getattr(audit, "active_snapshot_version", 1),
                            defaults={
                                "requirement_node": assignment.requirement_node,
                                "framework": assignment.framework,
                                "spoc_user": assignment.spoc_user,
                                "is_active": True
                            }
                        )
                if fallback_snapshot:
                    AuditEvidenceLink.objects.create(
                        assessment_control=fallback_snapshot,
                        control_evidence_mapping=mapping,
                        evidence=evidence,
                        evidence_revision=revision,
                        evidence_requirement_snapshot=None,
                        review_status="PENDING_REVIEW",
                        reviewer_feedback="",
                        review_level=1,
                        expiry_warning=False,
                        is_active=True,
                    )
                    links_created = 1

            RequirementAssessment.objects.filter(
                requirement=assignment.requirement_node
            ).update(
                status="in_review",
                result="not_assessed",
                observation="",
            )

            NotificationService.notify_evidence_submission(mapping)

        return Response({
            "status": "success",
            "success": True,
            "evidence_id": str(evidence.id),
            "revision_id": str(revision.id),
            "mapping_id": str(mapping.id),
            "links_created": links_created,
            "review_status": "PENDING_REVIEW",
            "is_active": True,
        }, status=status.HTTP_201_CREATED)


class EvidenceReviewActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, link_id):
        """
        Reviewer evidence approval/rejection with optimistic locking (rich 409 response on conflict - BS-12 / BS-17).
        """
        user = request.user
        review_action = request.data.get("status")  # APPROVED or REJECTED
        feedback = request.data.get("feedback", "").strip()
        version = request.data.get("version")

        link = AuditEvidenceLink.objects.filter(id=link_id).first()
        if not link:
            return Response({"error": "Evidence link not found."}, status=status.HTTP_404_NOT_FOUND)

        # Server-side Authorization Enforcement for Evidence Review
        assignment = link.control_evidence_mapping.control_assignment if link.control_evidence_mapping else (
            link.assessment_control.control_assignment if link.assessment_control else None
        )
        is_reviewer = bool(assignment and assignment.reviewer_user and assignment.reviewer_user == user)
        is_admin_or_higher = bool(
            getattr(user, "is_superuser", False) or getattr(user, "platform_role", "") in ["superadmin", "webadmin", "admin"] or getattr(user, "is_admin", False)
        )
        if not (is_admin_or_higher or is_reviewer):
            return Response(
                {"error": "Permission denied. Only authorized reviewers can perform evidence review."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Safe Optimistic Locking Check (BS-17)
        if version is not None:
            try:
                version_int = int(version)
                if link.version != version_int:
                    return Response({
                        "error": "Conflict",
                        "message": "This evidence review was modified by another reviewer concurrently. Please refresh.",
                        "current_version": link.version,
                    }, status=status.HTTP_409_CONFLICT)
            except (ValueError, TypeError):
                pass

        is_approved = review_action == "APPROVED"
        expiry_date = request.data.get("expiry_date")

        with transaction.atomic():
            link.review_status = "APPROVED" if is_approved else "REJECTED"
            link.reviewer_feedback = feedback
            link.reviewed_by = user
            link.reviewed_at = timezone.now()
            link.version += 1

            if link.evidence:
                if is_approved:
                    if expiry_date and str(expiry_date).strip():
                        link.evidence.expiry_date = expiry_date
                    link.evidence.status = "valid"
                else:
                    link.evidence.status = "in_review"
                link.evidence.save()

            link.save()

            assignment = link.control_evidence_mapping.control_assignment if link.control_evidence_mapping else (
                link.assessment_control.control_assignment if link.assessment_control else None
            )
            node = link.assessment_control.requirement_node if (link.assessment_control and link.assessment_control.requirement_node) else (
                assignment.requirement_node if assignment else None
            )
            if node:
                RequirementAssessment.objects.filter(requirement=node).update(
                    status="done" if is_approved else "in_progress",
                    result="compliant" if is_approved else "non_compliant",
                    observation=feedback,
                )

            try:
                NotificationService.notify_reviewer_decision(link, approved=is_approved)
            except Exception:
                pass

        return Response({
            "status": "success",
            "link_id": str(link.id),
            "review_status": link.review_status,
            "version": link.version,
        })


class EvidenceRepositoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Search-first evidence repository (BS-8 / BS-11).
        Supports search, filters, pagination, and dynamic virtual tree view.
        """
        query = request.query_params.get("q", "")
        framework_id = request.query_params.get("framework_id")
        assessment_id = request.query_params.get("assessment_id")
        review_status = request.query_params.get("review_status")
        spoc_user_id = request.query_params.get("spoc_user_id")
        expiry_warning = request.query_params.get("expiry_warning") == "true"
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        filters = {
            "framework_id": framework_id,
            "assessment_id": assessment_id,
            "review_status": review_status,
            "spoc_user_id": spoc_user_id,
            "expiry_warning": expiry_warning,
        }

        data = SearchService.search_evidence(query=query, filters=filters, page=page, page_size=page_size)

        # Format output list
        results_formatted = []
        for link in data["results"]:
            req_snap = link.evidence_requirement_snapshot
            assignment = link.control_evidence_mapping.control_assignment if link.control_evidence_mapping else (
                link.assessment_control.control_assignment if link.assessment_control else None
            )
            node = link.assessment_control.requirement_node if (link.assessment_control and link.assessment_control.requirement_node) else (
                assignment.requirement_node if (assignment and assignment.requirement_node) else None
            )
            framework = link.assessment_control.framework if (link.assessment_control and link.assessment_control.framework) else (
                assignment.framework if (assignment and assignment.framework) else None
            )
            spoc_user = link.assessment_control.spoc_user if (link.assessment_control and link.assessment_control.spoc_user) else (
                assignment.spoc_user if assignment else None
            )
            reviewer_user = assignment.reviewer_user if assignment else None

            domain_node = RequirementNode.objects.filter(urn=node.parent_urn).first() if (node and node.parent_urn) else None
            domain_name = domain_node.name if domain_node else (f"Domain {node.ref_id.split('.')[0]}" if (node and node.ref_id and "." in node.ref_id) else "General Domain")

            results_formatted.append({
                "id": str(link.id),
                "evidence_id": str(link.evidence.id) if link.evidence else None,
                "title": link.evidence.name if link.evidence else "Evidence Document",
                "description": link.evidence.description if link.evidence else "",
                "expiry_date": link.evidence.expiry_date.isoformat() if (link.evidence and link.evidence.expiry_date) else None,
                "file_url": f"/api/evidences/{link.evidence.id}/attachment/" if (link.evidence and link.evidence_revision and link.evidence_revision.attachment) else None,
                "review_status": link.review_status,
                "reviewer_feedback": link.reviewer_feedback,
                "expiry_warning": link.expiry_warning,
                "version": link.version,
                "control": {
                    "ref_id": node.ref_id if node else "N/A",
                    "name": node.name if node else "",
                    "description": node.description if node else "",
                    "framework": framework.name if framework else "General Framework",
                    "framework_id": str(framework.id) if framework else "",
                    "domain": domain_name,
                    "spoc": spoc_user.email if spoc_user else None,
                    "reviewer": reviewer_user.email if reviewer_user else None,
                },
                "requirement": {
                    "name": req_snap.name if req_snap else (
                        link.control_evidence_mapping.evidence_requirement.name if (link.control_evidence_mapping and link.control_evidence_mapping.evidence_requirement) else ""
                    ),
                    "description": req_snap.description if req_snap else (
                        link.control_evidence_mapping.evidence_requirement.description if (link.control_evidence_mapping and link.control_evidence_mapping.evidence_requirement) else ""
                    ),
                },
                "assessment": {
                    "id": str(link.assessment_control.compliance_assessment.id) if (link.assessment_control and link.assessment_control.compliance_assessment) else "",
                    "name": link.assessment_control.compliance_assessment.name if (link.assessment_control and link.assessment_control.compliance_assessment) else "General Assessment",
                    "audit_period": link.assessment_control.compliance_assessment.audit_period_year if (link.assessment_control and link.assessment_control.compliance_assessment) else 2026,
                    "phase": link.assessment_control.compliance_assessment.audit_phase if (link.assessment_control and link.assessment_control.compliance_assessment) else "EVIDENCE_COLLECTION",
                }
            })

        # Build complete framework -> domain -> control tree from database
        import re
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s or '')]

        frameworks_tree = []
        for fw in Framework.objects.all():
            fw_domains = {}
            req_nodes = list(RequirementNode.objects.filter(framework=fw))
            req_nodes.sort(key=lambda n: natural_sort_key(n.ref_id))
            urn_map = {n.urn: n for n in req_nodes}

            for node in req_nodes:
                if not node.assessable:
                    continue
                dom_node = urn_map.get(node.parent_urn) if node.parent_urn else None
                dom_name = dom_node.name if dom_node else (f"Domain {node.ref_id.split('.')[0]}" if (node.ref_id and "." in node.ref_id) else "General Domain")

                if dom_name not in fw_domains:
                    fw_domains[dom_name] = []
                fw_domains[dom_name].append({
                    "ref_id": node.ref_id,
                    "name": node.name,
                    "domain": dom_name,
                })

            domains_formatted = []
            for dom_name, ctrls in fw_domains.items():
                ctrls.sort(key=lambda c: natural_sort_key(c["ref_id"]))
                domains_formatted.append({"name": dom_name, "controls": ctrls})
            domains_formatted.sort(key=lambda d: natural_sort_key(d["name"]))
            frameworks_tree.append({
                "id": str(fw.id),
                "name": fw.name,
                "domains": domains_formatted,
            })

        return Response({
            "total": data["total"],
            "page": data["page"],
            "page_size": data["page_size"],
            "results": results_formatted,
            "frameworks_tree": frameworks_tree,
        })


class EvidenceCopyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Cross-audit evidence copy endpoint (BS-3 / v5.1).
        Copies evidence to a target audit → ALWAYS creates AuditEvidenceLink with PENDING_REVIEW.
        Uses deterministic requirement matching (OS-4 / v5.1).
        """
        user = request.user
        source_link_id = request.data.get("source_link_id")
        target_assessment_id = request.data.get("target_assessment_id")

        if getattr(user, "platform_role", "") not in ["superadmin", "webadmin"]:
            return Response({"error": "Only Webadmin or Superadmin can copy evidence between audits."}, status=status.HTTP_403_FORBIDDEN)

        if not source_link_id or not target_assessment_id:
            return Response({"error": "source_link_id and target_assessment_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        source_link = AuditEvidenceLink.objects.filter(id=source_link_id, is_active=True).first()
        target_assessment = ComplianceAssessment.objects.filter(id=target_assessment_id).first()

        if not source_link or not target_assessment:
            return Response({"error": "Source link or target assessment not found."}, status=status.HTTP_404_NOT_FOUND)

        req_node = source_link.assessment_control.requirement_node
        target_snapshot = AssessmentControlSnapshot.objects.filter(
            compliance_assessment=target_assessment,
            requirement_node=req_node,
            snapshot_version=target_assessment.active_snapshot_version,
            is_active=True
        ).first()

        if not target_snapshot:
            return Response({"error": f"Control '{req_node.ref_id}' is not in the scope of target assessment '{target_assessment.name}'."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Deterministic requirement matching (OS-4 / v5.1)
            matched_req = map_requirement_snapshot(target_snapshot, source_link.evidence_requirement_snapshot)

            expiry_warn = False
            if source_link.evidence.expiry_date and target_assessment.audit_end_date:
                expiry_warn = source_link.evidence.expiry_date < target_assessment.audit_end_date

            new_link, created = AuditEvidenceLink.objects.get_or_create(
                assessment_control=target_snapshot,
                evidence_revision=source_link.evidence_revision,
                review_level=1,
                defaults={
                    "control_evidence_mapping": source_link.control_evidence_mapping,
                    "evidence": source_link.evidence,
                    "evidence_requirement_snapshot": matched_req,
                    "review_status": "PENDING_REVIEW",  # Always reset to pending
                    "expiry_warning": expiry_warn,
                }
            )

        return Response({
            "status": "success",
            "link_id": str(new_link.id),
            "review_status": new_link.review_status,
            "target_assessment": target_assessment.name,
        })


class EvidenceDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, link_id):
        """
        Evidence deletion endpoint for Webadmins, Admins, and Superadmins.
        Deletes the evidence link & mapping, resets requirement assessment, and records full audit logs.
        """
        user = request.user
        role = getattr(user, "platform_role", "")
        is_admin_user = user.is_superuser or role in ["superadmin", "webadmin", "admin"]
        if not is_admin_user:
            return Response({"error": "Only Webadmins, Admins, or Superadmins can delete evidence documents."}, status=status.HTTP_403_FORBIDDEN)

        link = AuditEvidenceLink.objects.filter(id=link_id).first()
        if not link:
            return Response({"error": "Evidence document link not found."}, status=status.HTTP_404_NOT_FOUND)

        evidence = link.evidence
        mapping = link.control_evidence_mapping
        assignment = mapping.control_assignment if mapping else (
            link.assessment_control.control_assignment if link.assessment_control else None
        )
        node = link.assessment_control.requirement_node if (link.assessment_control and link.assessment_control.requirement_node) else (
            assignment.requirement_node if (assignment and assignment.requirement_node) else None
        )
        ref_id = node.ref_id if node else "N/A"
        evidence_title = evidence.name if evidence else "Evidence Document"

        # Check due date restriction: Cannot delete evidence if past the audit due date
        import datetime
        today = datetime.date.today()
        audit = link.assessment_control.compliance_assessment if link.assessment_control else None
        due_date_val = audit.due_date if (audit and audit.due_date) else (assignment.due_date if (assignment and assignment.due_date) else None)
        if isinstance(due_date_val, datetime.datetime):
            due_date_val = due_date_val.date()

        if due_date_val and today > due_date_val:
            return Response(
                {"error": f"Evidence deletion dis-allowed: Past the audit due date ({due_date_val.strftime('%d/%m/%Y')})."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Notify SPOC if an active pending audit exists for this control
            if assignment and assignment.spoc_user:
                try:
                    from core.notification_service import NotificationService
                    NotificationService.notify(
                        user=assignment.spoc_user,
                        title=f"Evidence Deleted Notice - Control {ref_id}",
                        message=f"Notice: Evidence document '{evidence_title}' for control '{ref_id}' was deleted by {user.email}. Fresh evidence resubmission is required for pending audit.",
                        notification_type="EVIDENCE",
                        link_url="/control-assignments/submit",
                        send_email=True,
                    )
                except Exception as notif_err:
                    print(f"Deletion notification warning: {notif_err}")
            # 1. AuditLog / LogEntry recording
            try:
                from auditlog.models import LogEntry
                from django.contrib.contenttypes.models import ContentType
                import json

                LogEntry.objects.create(
                    content_type=ContentType.objects.get_for_model(evidence) if evidence else None,
                    object_pk=str(evidence.id) if evidence else str(link.id),
                    object_repr=f"Deleted Evidence '{evidence_title}' (Control {ref_id})",
                    action=2,  # DELETE = 2
                    actor=user,
                    changes={
                        "evidence_document": [evidence_title, "DELETED"],
                        "control_ref_id": [ref_id, ref_id],
                        "deleted_by": [user.email, user.email],
                    },
                )
            except Exception as log_err:
                print(f"LogEntry recording warning: {log_err}")

            # 2. AssignmentChangeLog recording
            if assignment:
                from core.models import AssignmentChangeLog
                AssignmentChangeLog.objects.create(
                    control_assignment=assignment,
                    action_type="MODIFIED",
                    field_changed="evidence_deleted",
                    reason=f"Deleted evidence '{evidence_title}'",
                    changed_by=user,
                )

            # 3. Soft-delete link & mapping, check if evidence can be removed
            link.is_active = False
            link.save()

            if mapping:
                other_active_links = AuditEvidenceLink.objects.filter(control_evidence_mapping=mapping, is_active=True).exists()
                if not other_active_links:
                    mapping.delete()

            if evidence:
                other_links = AuditEvidenceLink.objects.filter(evidence=evidence, is_active=True).exists()
                if not other_links:
                    evidence.delete()

            # 4. Reset RequirementAssessment status back to in_progress / not_assessed
            if node:
                other_approved = AuditEvidenceLink.objects.filter(
                    assessment_control__requirement_node=node,
                    review_status="APPROVED",
                    is_active=True
                ).exists()
                if not other_approved:
                    RequirementAssessment.objects.filter(requirement=node).update(
                        status="in_progress",
                        result="not_assessed",
                        observation="Evidence document was deleted by administrator.",
                    )

            import structlog
            structlog.getLogger(__name__).info(
                "Evidence document deleted by admin",
                user=user.email,
                evidence_title=evidence_title,
                control_ref=ref_id,
                link_id=str(link_id),
            )

        return Response({
            "status": "success",
            "message": f"Evidence '{evidence_title}' deleted successfully and action recorded in audit logs.",
        })

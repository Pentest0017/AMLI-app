import uuid
from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import (
    ControlAssignment,
    EvidenceRequirement,
    RequirementNode,
    Framework,
    User,
    AssignmentChangeLog,
    AuditEvidenceLink,
)
from core.permissions import IsGlobalAdmin
from core.notification_service import NotificationService
from core.audit_lifecycle import get_active_evidence_link
from core.escalation_engine import compute_current_escalation_level


def sync_control_assignments_to_audit_assignments():
    from core.models import ControlAssignment, RequirementAssignment, RequirementAssessment, ComplianceAssessment, Actor
    synced = 0
    for ca in ControlAssignment.objects.filter(is_active=True).select_related('requirement_node', 'framework', 'spoc_user'):
        if not ca.spoc_user:
            continue
        actor, _ = Actor.objects.get_or_create(user=ca.spoc_user)
        if ca.framework:
            audits = list(ComplianceAssessment.objects.filter(Q(framework=ca.framework) | Q(framework__isnull=True)))
        else:
            audits = list(ComplianceAssessment.objects.all())

        for audit in audits:
            if audit.requirement_assessments.count() == 0:
                try:
                    audit.create_requirement_assessments()
                except Exception:
                    pass

            ras = RequirementAssessment.objects.filter(compliance_assessment=audit, requirement=ca.requirement_node)
            if not ras.exists():
                continue

            req_assignment = RequirementAssignment.objects.filter(compliance_assessment=audit, actor=actor).first()
            if not req_assignment:
                req_assignment = RequirementAssignment.objects.create(
                    compliance_assessment=audit,
                    status=RequirementAssignment.Status.IN_PROGRESS,
                    folder=audit.folder
                )
                req_assignment.actor.add(actor)

            for ra in ras:
                req_assignment.requirement_assessments.add(ra)
            synced += 1
    return synced


class ControlAssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = ControlAssignment.objects.all().select_related(
        "requirement_node", "framework", "spoc_user", "reviewer_user"
    ).prefetch_related("evidence_requirements")

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset().filter(is_active=True)

        user_role = getattr(user, "platform_role", "")
        if getattr(user, "is_superuser", False) or user_role in ["superadmin", "webadmin"]:
            return qs

        # For admin and user: only show controls where they are SPOC or Reviewer or have assigned domain access
        from django.db import models
        from iam.models import RoleAssignment, Folder
        accessible_folders = RoleAssignment.get_accessible_folder_ids(Folder.get_root_folder(), user, Folder.ContentType.DOMAIN)
        return qs.filter(
            models.Q(spoc_user=user) | 
            models.Q(reviewer_user=user) | 
            models.Q(assessment_control__assessment__domain_id__in=accessible_folders)
        ).distinct()

    @action(detail=False, methods=["get"], url_path="controls")
    def list_controls(self, request):
        """
        Dynamically extracts assessable controls from loaded libraries in the database.
        Not hardcoded — updates as libraries change.
        """
        framework_id = request.query_params.get("framework_id")
        all_frameworks = list(Framework.objects.filter(requirement_nodes__assessable=True).distinct().order_by("name"))

        controls_qs = RequirementNode.objects.filter(assessable=True).select_related("framework")
        if framework_id:
            controls_qs = controls_qs.filter(framework_id=framework_id)

        user = request.user
        is_super_or_webadmin = bool(
            getattr(user, "is_superuser", False) or getattr(user, "platform_role", "") in ["superadmin", "webadmin"]
        )

        framework_data = []
        for fw in all_frameworks:
            total_count = RequirementNode.objects.filter(framework=fw, assessable=True).count()
            if framework_id and str(fw.id) != str(framework_id):
                framework_data.append({
                    "id": str(fw.id),
                    "name": fw.name,
                    "urn": fw.urn,
                    "controls_count": total_count,
                    "controls": [],
                })
                continue

            fw_controls = list(controls_qs.filter(framework=fw).order_by("order_id"))
            parent_urns = [c.parent_urn for c in fw_controls if c.parent_urn]
            domains_map = {
                n.urn: n.name for n in RequirementNode.objects.filter(urn__in=parent_urns)
            }

            fw_node_ids = [c.id for c in fw_controls]
            assignments_qs = ControlAssignment.objects.filter(
                requirement_node_id__in=fw_node_ids, is_active=True
            ).select_related("spoc_user", "reviewer_user").prefetch_related("evidence_requirements")

            assignments_map = {ca.requirement_node_id: ca for ca in assignments_qs}
            ca_ids = [ca.id for ca in assignments_map.values()]

            links_qs = AuditEvidenceLink.objects.filter(
                Q(control_evidence_mapping__control_assignment_id__in=ca_ids) | Q(assessment_control__control_assignment_id__in=ca_ids),
                is_active=True
            ).select_related("evidence", "evidence_revision", "reviewed_by", "control_evidence_mapping", "evidence_requirement_snapshot").order_by("-created_at")

            links_by_ca = {}
            for link_obj in links_qs:
                ca_id_val = getattr(link_obj.control_evidence_mapping, "control_assignment_id", None) or (link_obj.assessment_control.control_assignment_id if link_obj.assessment_control else None)
                if ca_id_val:
                    links_by_ca.setdefault(ca_id_val, []).append(link_obj)

            controls_list = []
            for c in fw_controls:
                domain_name = domains_map.get(c.parent_urn, "General")
                assignment = assignments_map.get(c.id)

                if not is_super_or_webadmin:
                    if not assignment or not assignment.spoc_user or assignment.spoc_user != user:
                        continue

                ca_links = links_by_ca.get(assignment.id, []) if assignment else []
                gen_link = ca_links[0] if ca_links else None

                req_items = []
                if assignment:
                    active_reqs = [r for r in assignment.evidence_requirements.all() if r.is_active]
                    for r in active_reqs:
                        req_link = None
                        for l_cand in ca_links:
                            cand_req_id = getattr(l_cand.control_evidence_mapping, "evidence_requirement_id", None) or getattr(l_cand.evidence_requirement_snapshot, "source_requirement_id", None)
                            if cand_req_id == r.id:
                                req_link = l_cand
                                break
                        req_items.append({
                            "id": str(r.id),
                            "name": r.name,
                            "description": r.description,
                            "is_mandatory": r.is_mandatory,
                            "latest_link": (
                                {
                                    "id": str(req_link.id),
                                    "title": req_link.evidence.name,
                                    "version": str(req_link.evidence_revision.version) if req_link.evidence_revision else "1.0",
                                    "file_url": f"/evidences/{req_link.evidence.id}/attachment" if (req_link.evidence and req_link.evidence_revision and req_link.evidence_revision.attachment) else None,
                                    "review_status": req_link.review_status,
                                    "reviewer_feedback": req_link.reviewer_feedback,
                                    "reviewed_by": req_link.reviewed_by.email if req_link.reviewed_by else None,
                                    "reviewed_at": req_link.reviewed_at.isoformat() if req_link.reviewed_at else None,
                                }
                                if req_link
                                else None
                            )
                        })

                controls_list.append({
                    "id": str(c.id),
                    "ref_id": c.ref_id,
                    "name": c.name,
                    "domain_name": domain_name,
                    "description": c.description,
                    "order_id": c.order_id,
                    "assignment": {
                        "id": str(assignment.id) if assignment else None,
                        "is_not_applicable": assignment.is_not_applicable if assignment else False,
                        "due_date": assignment.due_date.isoformat() if (assignment and assignment.due_date) else None,
                        "l1_reminder_date": assignment.l1_reminder_date.isoformat() if (assignment and assignment.l1_reminder_date) else None,
                        "l2_grace_deadline": assignment.l2_grace_deadline.isoformat() if (assignment and assignment.l2_grace_deadline) else None,
                        "l3_final_deadline": assignment.l3_final_deadline.isoformat() if (assignment and assignment.l3_final_deadline) else None,
                        "escalation_level": compute_current_escalation_level(assignment) if assignment else "ASSIGNED",
                        "spoc_user": {
                            "id": str(assignment.spoc_user.id),
                            "email": assignment.spoc_user.email,
                        } if assignment and assignment.spoc_user else None,
                        "reviewer_user": {
                            "id": str(assignment.reviewer_user.id),
                            "email": assignment.reviewer_user.email,
                        } if assignment and assignment.reviewer_user else None,
                        "evidence_requirements": req_items,
                        "latest_general_link": (
                            {
                                "id": str(gen_link.id),
                                "title": gen_link.evidence.name,
                                "version": str(gen_link.evidence_revision.version) if gen_link.evidence_revision else "1.0",
                                "file_url": f"/evidences/{gen_link.evidence.id}/attachment" if (gen_link.evidence and gen_link.evidence_revision and gen_link.evidence_revision.attachment) else None,
                                "review_status": gen_link.review_status,
                                "reviewer_feedback": gen_link.reviewer_feedback,
                                "reviewed_by": gen_link.reviewed_by.email if gen_link.reviewed_by else None,
                                "reviewed_at": gen_link.reviewed_at.isoformat() if gen_link.reviewed_at else None,
                            }
                            if gen_link
                            else None
                        )
                    }
                })

            framework_data.append({
                "id": str(fw.id),
                "name": fw.name,
                "urn": fw.urn,
                "controls_count": total_count,
                "controls": controls_list,
            })

        # Also get all potential SPOCs (role=user, admin, webadmin) and Reviewers (role=admin, webadmin)
        # Exclude superadmin (developer account)
        users = User.objects.filter(is_active=True).exclude(is_superuser=True)
        spocs = []
        reviewers = []
        for u in users:
            role = getattr(u, "platform_role", "")
            if role == "superadmin":
                continue
            spocs.append({
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": role,
            })
            if role in ["admin", "webadmin"] or getattr(u, "is_admin", False):
                reviewers.append({
                    "id": str(u.id),
                    "email": u.email,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "role": role,
                })

        return Response({
            "frameworks": framework_data,
            "spoc_users": spocs,
            "reviewer_users": reviewers,
        })

    def create(self, request, *args, **kwargs):
        """
        Creates or updates a ControlAssignment with evidence requirements.
        Only Webadmin/Superadmin can assign controls.
        """
        user = request.user
        is_admin_user = getattr(user, "is_superuser", False) or getattr(user, "platform_role", "") in ["superadmin", "webadmin", "admin"]
        if not is_admin_user:
            return Response({"error": "Only Admins, Webadmins, or Superadmins can assign controls."}, status=status.HTTP_403_FORBIDDEN)

        req_node_id = request.data.get("requirement_node_id")
        framework_id = request.data.get("framework_id")
        spoc_user_id = request.data.get("spoc_user_id") or None
        reviewer_user_id = request.data.get("reviewer_user_id") or None
        evidence_reqs = request.data.get("evidence_requirements", [])
        notes = request.data.get("notes", "")
        is_not_applicable = bool(request.data.get("is_not_applicable", False))

        if not req_node_id:
            return Response({"error": "requirement_node_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        req_node = RequirementNode.objects.filter(id=req_node_id).select_related("framework").first()
        if not req_node:
            return Response({"error": "Invalid requirement_node_id."}, status=status.HTTP_400_BAD_REQUEST)

        if not framework_id and req_node.framework_id:
            framework_id = str(req_node.framework_id)

        if not framework_id:
            return Response({"error": "framework_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            assignment, created = ControlAssignment.objects.get_or_create(
                requirement_node=req_node,
                framework_id=framework_id,
                defaults={
                    "spoc_user_id": spoc_user_id,
                    "reviewer_user_id": reviewer_user_id,
                    "assigned_by": user,
                    "notes": notes,
                    "is_not_applicable": is_not_applicable,
                }
            )

            if not created:
                prev_spoc = assignment.spoc_user
                prev_reviewer = assignment.reviewer_user

                assignment.spoc_user_id = spoc_user_id
                assignment.reviewer_user_id = reviewer_user_id
                assignment.notes = notes
                assignment.is_not_applicable = is_not_applicable
                assignment.is_active = True
                assignment.save()

                # Log changes
                if prev_spoc != assignment.spoc_user:
                    AssignmentChangeLog.objects.create(
                        control_assignment=assignment,
                        action_type="MODIFIED",
                        field_changed="spoc_user",
                        previous_user=prev_spoc,
                        new_user=assignment.spoc_user,
                        changed_by=user,
                    )
                if prev_reviewer != assignment.reviewer_user:
                    AssignmentChangeLog.objects.create(
                        control_assignment=assignment,
                        action_type="MODIFIED",
                        field_changed="reviewer_user",
                        previous_user=prev_reviewer,
                        new_user=assignment.reviewer_user,
                        changed_by=user,
                    )
            else:
                AssignmentChangeLog.objects.create(
                    control_assignment=assignment,
                    action_type="CREATED",
                    changed_by=user,
                )

            # Update evidence requirements
            existing_reqs = {r.name: r for r in assignment.evidence_requirements.filter(is_active=True)}
            keep_ids = []

            for idx, er in enumerate(evidence_reqs):
                er_name = er.get("name", "").strip()
                if not er_name:
                    continue

                if er_name in existing_reqs:
                    req_obj = existing_reqs[er_name]
                    req_obj.description = er.get("description", "")
                    req_obj.is_mandatory = er.get("is_mandatory", True)
                    req_obj.order = idx
                    req_obj.save()
                    keep_ids.append(req_obj.id)
                else:
                    new_req = EvidenceRequirement.objects.create(
                        control_assignment=assignment,
                        name=er_name,
                        description=er.get("description", ""),
                        is_mandatory=er.get("is_mandatory", True),
                        order=idx,
                    )
                    keep_ids.append(new_req.id)

            # Soft-delete removed requirements
            for r in assignment.evidence_requirements.filter(is_active=True):
                if r.id not in keep_ids:
                    r.soft_delete()

            # Save due_date if provided
            due_date_val = request.data.get("due_date")
            if due_date_val:
                assignment.due_date = due_date_val
                assignment.save(update_fields=["due_date"])

            # Queue control assignment into persistent batching queue & dispatch in-app notifications
            if assignment.spoc_user:
                from core.assignment_batching import queue_control_assignment
                queue_control_assignment(assignment)

                ref_id = assignment.requirement_node.ref_id if assignment.requirement_node else "N/A"
                ctrl_name = assignment.requirement_node.name if assignment.requirement_node else "Control"
                NotificationService.notify(
                    user=assignment.spoc_user,
                    title=f"New Control Assignment: {ref_id}",
                    message=f"You have been assigned as SPOC for control {ref_id} ({ctrl_name}) by {user.email}.",
                    notification_type="ASSIGNMENT",
                    link_url="/control-assignments/submit",
                    send_email=True,
                    related_object_type="ControlAssignment",
                    related_object_id=str(assignment.id),
                )

            if assignment.reviewer_user and assignment.reviewer_user != assignment.spoc_user:
                ref_id = assignment.requirement_node.ref_id if assignment.requirement_node else "N/A"
                ctrl_name = assignment.requirement_node.name if assignment.requirement_node else "Control"
                NotificationService.notify(
                    user=assignment.reviewer_user,
                    title=f"New Reviewer Assignment: {ref_id}",
                    message=f"You have been assigned as Reviewer for control {ref_id} ({ctrl_name}) by {user.email}.",
                    notification_type="ASSIGNMENT",
                    link_url="/control-assignments/review",
                    send_email=True,
                    related_object_type="ControlAssignment",
                    related_object_id=str(assignment.id),
                )

            sync_control_assignments_to_audit_assignments()

        return Response({
            "id": str(assignment.id),
            "status": "success",
            "message": "Control assignment saved successfully."
        })

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_assign(self, request):
        """
        All-or-nothing bulk assignment with detailed validation report (BS-6).
        """
        user = request.user
        is_admin_user = getattr(user, "is_superuser", False) or getattr(user, "platform_role", "") in ["superadmin", "webadmin", "admin"]
        if not is_admin_user:
            return Response({"error": "Only Admins, Webadmins, or Superadmins can bulk assign."}, status=status.HTTP_403_FORBIDDEN)

        assignments_data = request.data.get("assignments", [])
        if not assignments_data:
            return Response({"error": "assignments array is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Phase 1: Validation
        validation_errors = []
        for idx, item in enumerate(assignments_data):
            req_id = item.get("requirement_node_id")
            fw_id = item.get("framework_id")
            if not req_id or not fw_id:
                validation_errors.append({"index": idx, "error": "requirement_node_id and framework_id are required."})
                continue

            if item.get("spoc_user_id"):
                spoc = User.objects.filter(id=item["spoc_user_id"], is_active=True).first()
                if not spoc:
                    validation_errors.append({"index": idx, "error": f"SPOC user {item['spoc_user_id']} not found."})

            if item.get("reviewer_user_id"):
                rev = User.objects.filter(id=item["reviewer_user_id"], is_active=True).first()
                if not rev:
                    validation_errors.append({"index": idx, "error": f"Reviewer user {item['reviewer_user_id']} not found."})

        if validation_errors:
            return Response({
                "status": "validation_failed",
                "total": len(assignments_data),
                "errors": validation_errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Phase 2: Execution inside transaction
        bulk_op_id = uuid.uuid4()
        created_count = 0

        with transaction.atomic():
            for item in assignments_data:
                ca, created = ControlAssignment.objects.get_or_create(
                    requirement_node_id=item["requirement_node_id"],
                    framework_id=item["framework_id"],
                    defaults={
                        "spoc_user_id": item.get("spoc_user_id"),
                        "reviewer_user_id": item.get("reviewer_user_id"),
                        "assigned_by": user,
                        "notes": item.get("notes", ""),
                    }
                )
                if created:
                    created_count += 1
                else:
                    ca.spoc_user_id = item.get("spoc_user_id")
                    ca.reviewer_user_id = item.get("reviewer_user_id")
                    ca.notes = item.get("notes", "")
                    ca.is_active = True
                    ca.save()

                AssignmentChangeLog.objects.create(
                    control_assignment=ca,
                    action_type="BULK_ASSIGNED",
                    changed_by=user,
                    bulk_operation_id=bulk_op_id,
                )

                # Process evidence requirements if provided
                if "evidence_requirements" in item:
                    for r_idx, er in enumerate(item["evidence_requirements"]):
                        er_name = er.get("name", "").strip()
                        if er_name:
                            EvidenceRequirement.objects.get_or_create(
                                control_assignment=ca,
                                name=er_name,
                                defaults={
                                    "description": er.get("description", ""),
                                    "is_mandatory": er.get("is_mandatory", True),
                                    "order": r_idx,
                                }
                            )

                # Save due_date if provided
                if item.get("due_date"):
                    ca.due_date = item["due_date"]
                    ca.save(update_fields=["due_date"])

                if ca.spoc_user:
                    from core.assignment_batching import queue_control_assignment
                    queue_control_assignment(ca)

                    ref_id = ca.requirement_node.ref_id if ca.requirement_node else "N/A"
                    ctrl_name = ca.requirement_node.name if ca.requirement_node else "Control"
                    NotificationService.notify(
                        user=ca.spoc_user,
                        title=f"New Control Assignment: {ref_id}",
                        message=f"You have been assigned as SPOC for control {ref_id} ({ctrl_name}) by {user.email}.",
                        notification_type="ASSIGNMENT",
                        link_url="/control-assignments/submit",
                        send_email=True,
                        related_object_type="ControlAssignment",
                        related_object_id=str(ca.id),
                    )

                if ca.reviewer_user and ca.reviewer_user != ca.spoc_user:
                    ref_id = ca.requirement_node.ref_id if ca.requirement_node else "N/A"
                    ctrl_name = ca.requirement_node.name if ca.requirement_node else "Control"
                    NotificationService.notify(
                        user=ca.reviewer_user,
                        title=f"New Reviewer Assignment: {ref_id}",
                        message=f"You have been assigned as Reviewer for control {ref_id} ({ctrl_name}) by {user.email}.",
                        notification_type="ASSIGNMENT",
                        link_url="/control-assignments/review",
                        send_email=True,
                        related_object_type="ControlAssignment",
                        related_object_id=str(ca.id),
                    )

            sync_control_assignments_to_audit_assignments()

        return Response({
            "status": "success",
            "bulk_operation_id": str(bulk_op_id),
            "processed": len(assignments_data),
            "created": created_count,
        })

    @action(detail=False, methods=["post"], url_path="toggle-na")
    def toggle_na(self, request):
        req_node_id = request.data.get("requirement_node_id")
        framework_id = request.data.get("framework_id")
        is_na = request.data.get("is_not_applicable")
        if not req_node_id or not framework_id:
            return Response({"error": "requirement_node_id and framework_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        assignment = ControlAssignment.objects.filter(requirement_node_id=req_node_id, framework_id=framework_id).order_by('-updated_at').first()
        if not assignment:
            assignment = ControlAssignment.objects.create(
                requirement_node_id=req_node_id,
                framework_id=framework_id,
                assigned_by=request.user,
                is_not_applicable=True if is_na is None else bool(is_na)
            )
        else:
            if is_na is None:
                assignment.is_not_applicable = not assignment.is_not_applicable
            else:
                assignment.is_not_applicable = bool(is_na)
            assignment.save()

        return Response({"status": "success", "is_not_applicable": assignment.is_not_applicable})


from rest_framework.views import APIView

class AssignmentSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsGlobalAdmin]

    def get(self, request):
        from core.assignment_batching import get_configured_batching_window_hours
        hours = get_configured_batching_window_hours()
        return Response({"window_hours": hours})

    def post(self, request):
        from core.assignment_batching import set_configured_batching_window_hours, get_configured_batching_window_hours
        hours = request.data.get("window_hours")
        if hours is not None:
            set_configured_batching_window_hours(hours)
        return Response({"status": "success", "window_hours": get_configured_batching_window_hours()})

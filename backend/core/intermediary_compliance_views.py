import copy
from datetime import datetime
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
import weasyprint

from django.core.files.storage import default_storage
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from core.models import (
    IntermediaryFolder,
    IntermediaryDomainAssignment,
    IntermediaryPartnerReport,
    IntermediaryGeneratedReport,
    Notification,
    User,
)
from core.notification_views import FlexibleTokenAuthentication
from core.serializers import BaseModelSerializer


def is_user_admin(user):
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, 'platform_role', '')
    return bool(getattr(user, 'is_superuser', False) or role in ['webadmin', 'superadmin'])


def get_intermediary_compliance_summary(scope_type="FULL", scope_id=None, user=None):
    """
    Authoritative single backend service for calculating Intermediary Compliance summary metrics,
    business function breakdowns, partner breakdowns, and attention sections.
    """
    root = IntermediaryFolder.get_root_repository()
    is_admin = is_user_admin(user)

    # Determine user-accessible domain folders
    spoc_domain_ids = set(
        IntermediaryDomainAssignment.objects.filter(spoc_users=user).values_list("domain_folder_id", flat=True)
    ) if user and not is_admin else set()

    reviewer_domain_ids = set(
        IntermediaryDomainAssignment.objects.filter(approving_admins=user).values_list("domain_folder_id", flat=True)
    ) if user and not is_admin else set()

    user_accessible_domain_ids = spoc_domain_ids | reviewer_domain_ids

    # Query all domain folders
    all_domain_qs = IntermediaryFolder.objects.filter(folder_type=IntermediaryFolder.FolderType.DOMAIN).select_related("parent")
    if user and not is_admin:
        all_domain_qs = all_domain_qs.filter(id__in=user_accessible_domain_ids)

    # Filter target domain folders by scope
    scope_type = (scope_type or "FULL").upper()
    target_name = "Full Repository Scope"
    reporting_period = "All Available Years"

    if scope_type == "YEAR" and scope_id:
        try:
            year_folder = IntermediaryFolder.objects.get(id=scope_id, folder_type=IntermediaryFolder.FolderType.YEAR)
            domain_folders = list(all_domain_qs.filter(parent=year_folder))
            target_name = f"Year: {year_folder.name}"
            reporting_period = year_folder.name
        except IntermediaryFolder.DoesNotExist:
            domain_folders = list(all_domain_qs)
    elif scope_type == "DOMAIN" and scope_id:
        try:
            domain_folder = all_domain_qs.get(id=scope_id)
            domain_folders = [domain_folder]
            target_name = f"Business Function: {domain_folder.name}"
            reporting_period = domain_folder.parent.name if domain_folder.parent else "All Available Years"
        except IntermediaryFolder.DoesNotExist:
            domain_folders = list(all_domain_qs)
    else:
        scope_type = "FULL"
        domain_folders = list(all_domain_qs)

    total_assigned = 0
    pending_evidence_count = 0
    under_review_count = 0
    approved_count = 0
    rejected_count = 0

    partner_breakdown = []
    bf_metrics_map = {}

    for df in domain_folders:
        bf_metrics_map[str(df.id)] = {
            "domain_id": str(df.id),
            "domain_name": df.name,
            "year_name": df.parent.name if df.parent else "N/A",
            "total_assigned": 0,
            "pending_evidence": 0,
            "under_review": 0,
            "approved": 0,
            "rejected": 0,
            "compliance_rate": 0.0,
            "coverage": 0.0,
        }

    for df in domain_folders:
        domain_id_str = str(df.id)
        bf_entry = bf_metrics_map.get(domain_id_str)

        # Child partners under this domain folder
        child_partners = list(
            IntermediaryFolder.objects.filter(
                parent=df,
                folder_type=IntermediaryFolder.FolderType.PARTNER
            ).select_related("parent", "parent__parent")
        )

        # Target entities to measure: child partner folders if present, else the domain folder itself
        target_units = child_partners if child_partners else [df]

        # Fetch active domain assignment (SPOCs and Reviewers)
        assignment = IntermediaryDomainAssignment.objects.filter(domain_folder_id=df.id).prefetch_related("spoc_users", "approving_admins").first()
        spoc_names = ", ".join([u.username or u.email for u in assignment.spoc_users.all()]) if assignment and assignment.spoc_users.exists() else "Unassigned"
        reviewer_names = ", ".join([u.username or u.email for u in assignment.approving_admins.all()]) if assignment and assignment.approving_admins.exists() else "Unassigned"

        for unit in target_units:
            total_assigned += 1
            if bf_entry:
                bf_entry["total_assigned"] += 1

            # Fetch active report for this unit (or for the domain folder if attached directly)
            active_report = IntermediaryPartnerReport.objects.filter(partner_folder=unit, is_active=True).first()
            if not active_report and unit != df:
                active_report = IntermediaryPartnerReport.objects.filter(partner_folder=df, is_active=True).first()

            last_submitted_str = None
            last_reviewed_str = None
            status_label = "PENDING EVIDENCE"

            if active_report:
                last_submitted_str = active_report.created_at.strftime("%d %b %Y") if active_report.created_at else None
                last_reviewed_str = active_report.reviewed_at.strftime("%d %b %Y") if active_report.reviewed_at else None

                if active_report.approval_status == IntermediaryPartnerReport.ApprovalStatus.PENDING_APPROVAL:
                    status_label = "UNDER REVIEW"
                    under_review_count += 1
                    if bf_entry:
                        bf_entry["under_review"] += 1
                elif active_report.approval_status == IntermediaryPartnerReport.ApprovalStatus.APPROVED:
                    status_label = "APPROVED / COMPLIANT"
                    approved_count += 1
                    if bf_entry:
                        bf_entry["approved"] += 1
                elif active_report.approval_status == IntermediaryPartnerReport.ApprovalStatus.REJECTED:
                    status_label = "REJECTED / NON-COMPLIANT"
                    rejected_count += 1
                    if bf_entry:
                        bf_entry["rejected"] += 1
            else:
                pending_evidence_count += 1
                if bf_entry:
                    bf_entry["pending_evidence"] += 1

            unit_name = unit.name if unit != df else f"{df.name} Domain"
            year_str = df.parent.name if df.parent else "N/A"

            partner_breakdown.append({
                "partner_id": str(unit.id),
                "partner_name": unit_name,
                "domain_name": df.name,
                "year_name": year_str,
                "status": status_label,
                "spoc": spoc_names,
                "reviewer": reviewer_names,
                "last_submitted": last_submitted_str,
                "last_reviewed": last_reviewed_str,
                "report_title": active_report.title if active_report else None,
                "report_id": str(active_report.id) if active_report else None,
            })

    # Finalize Business Function breakdown percentages
    business_function_breakdown = list(bf_metrics_map.values())
    for bfe in business_function_breakdown:
        tot = bfe["total_assigned"]
        if tot > 0:
            bfe["compliance_rate"] = round((bfe["approved"] / tot) * 100, 1)
            bfe["coverage"] = round(((bfe["approved"] + bfe["under_review"] + bfe["rejected"]) / tot) * 100, 1)

    # Compliance Rates for target scope
    approved_compliance_rate = round((approved_count / total_assigned * 100), 1) if total_assigned > 0 else 0.0
    compliance_coverage = round(((approved_count + under_review_count + rejected_count) / total_assigned * 100), 1) if total_assigned > 0 else 0.0

    # Non-Compliant / Attention lists
    non_compliant_business_functions = [
        bfe for bfe in business_function_breakdown if bfe["rejected"] > 0 or bfe["pending_evidence"] > 0 or bfe["under_review"] > 0
    ]
    non_compliant_partners = [
        pb for pb in partner_breakdown if pb["status"] in ("REJECTED / NON-COMPLIANT", "PENDING EVIDENCE", "UNDER REVIEW")
    ]

    return {
        "scope_type": scope_type,
        "scope_id": scope_id or "",
        "target_name": target_name,
        "reporting_period": reporting_period,
        "total_assigned": total_assigned,
        "pending_evidence_count": pending_evidence_count,
        "under_review_count": under_review_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "approved_compliance_rate": approved_compliance_rate,
        "compliance_coverage": compliance_coverage,
        "business_function_breakdown": business_function_breakdown,
        "partner_breakdown": partner_breakdown,
        "non_compliant_business_functions": non_compliant_business_functions,
        "non_compliant_partners": non_compliant_partners,
    }


from core.serializers import (
    BaseModelSerializer,
    IntermediaryFolderSerializer,
    IntermediaryFolderWriteSerializer,
)


class IntermediaryFolderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = IntermediaryFolderSerializer

    def get_queryset(self):
        user = self.request.user
        root = IntermediaryFolder.get_root_repository()

        if is_user_admin(user):
            return IntermediaryFolder.objects.all()

        spoc_domain_ids = set(
            IntermediaryDomainAssignment.objects.filter(spoc_users=user).values_list("domain_folder_id", flat=True)
        )
        reviewer_domain_ids = set(
            IntermediaryDomainAssignment.objects.filter(approving_admins=user).values_list("domain_folder_id", flat=True)
        )
        accessible_domain_ids = spoc_domain_ids | reviewer_domain_ids

        if len(accessible_domain_ids) > 0:
            assigned_domains = IntermediaryFolder.objects.filter(id__in=accessible_domain_ids)
            year_ids = set(assigned_domains.values_list("parent_id", flat=True))
            partner_ids = set(
                IntermediaryFolder.objects.filter(parent_id__in=accessible_domain_ids).values_list("id", flat=True)
            )
            unassigned_ids = set(IntermediaryFolder.objects.filter(Q(parent=root) | Q(parent_id__in=year_ids)).values_list("id", flat=True))
            accessible_ids = {root.id} | year_ids | accessible_domain_ids | partner_ids | unassigned_ids
            return IntermediaryFolder.objects.filter(id__in=accessible_ids)

        return IntermediaryFolder.objects.all()

    @action(detail=False, methods=["get"], url_path="tree")
    def repository_tree(self, request):
        root = IntermediaryFolder.get_root_repository()
        queryset = self.get_queryset()

        def build_node(folder):
            children = queryset.filter(parent=folder)
            serializer = IntermediaryFolderSerializer(folder, context={"request": request})
            data = serializer.data
            data["children"] = [build_node(child) for child in children]

            reports = IntermediaryPartnerReport.objects.filter(partner_folder=folder)
            data["reports"] = [
                {
                    "id": str(r.id),
                    "title": r.title,
                    "file_path": r.file_path,
                    "compliance_status": r.compliance_status,
                    "approval_status": r.approval_status,
                    "is_active": r.is_active,
                    "submitted_by": r.submitted_by.email if r.submitted_by else None,
                    "approved_by": r.approved_by.email if r.approved_by else None,
                    "reviewer_feedback": r.reviewer_feedback,
                    "expiry_date": str(r.expiry_date) if r.expiry_date else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                }
                for r in reports
            ]
            return data

        return Response(build_node(root))

    @action(detail=True, methods=["post"], url_path="copy-paste")
    def copy_paste(self, request, pk=None):
        source_folder = self.get_object()
        target_parent_id = request.data.get("target_parent_id")
        mode = request.data.get("mode", "COPY").upper()

        if target_parent_id:
            try:
                target_parent = IntermediaryFolder.objects.get(id=target_parent_id)
            except IntermediaryFolder.DoesNotExist:
                return Response({"error": "Target parent folder not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            target_parent = source_folder.parent or IntermediaryFolder.get_root_repository()

        with transaction.atomic():
            if mode == "CUT":
                source_folder.parent = target_parent
                source_folder.save()
                return Response(
                    IntermediaryFolderSerializer(source_folder, context={"request": request}).data,
                    status=status.HTTP_200_OK,
                )

            def duplicate_recursive(src, dest_parent):
                new_folder = IntermediaryFolder.objects.create(
                    name=f"{src.name} (Copy)" if dest_parent == src.parent else src.name,
                    description=src.description,
                    folder_type=src.folder_type,
                    parent=dest_parent,
                )
                if src.folder_type == IntermediaryFolder.FolderType.DOMAIN:
                    orig_assignment = src.assignments.first()
                    new_assignment = IntermediaryDomainAssignment.objects.create(domain_folder=new_folder)
                    if orig_assignment:
                        new_assignment.spoc_users.set(orig_assignment.spoc_users.all())
                        new_assignment.approving_admins.set(orig_assignment.approving_admins.all())

                for report in IntermediaryPartnerReport.objects.filter(partner_folder=src):
                    IntermediaryPartnerReport.objects.create(
                        partner_folder=new_folder,
                        title=report.title,
                        file_path=report.file_path,
                        submitted_by=report.submitted_by,
                        reviewer_feedback=report.reviewer_feedback,
                        compliance_status=report.compliance_status,
                        approval_status=report.approval_status,
                        expiry_date=report.expiry_date,
                        is_active=report.is_active,
                    )

                for child in src.children.all():
                    duplicate_recursive(child, new_folder)
                return new_folder

            copied_root = duplicate_recursive(source_folder, target_parent)

        return Response(
            IntermediaryFolderSerializer(copied_root, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class IntermediaryAssignmentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        domains = IntermediaryFolder.objects.filter(folder_type=IntermediaryFolder.FolderType.DOMAIN)
        results = []
        for domain in domains:
            assignment, _ = IntermediaryDomainAssignment.objects.get_or_create(domain_folder=domain)
            results.append({
                "domain_id": str(domain.id),
                "domain_name": domain.name,
                "year_name": domain.parent.name if domain.parent else "N/A",
                "spoc_users": [
                    {"id": str(u.id), "username": u.username or u.email, "email": u.email, "is_admin": u.is_admin or u.is_superuser or getattr(u, "platform_role", "") in ["admin", "webadmin", "superadmin"]}
                    for u in assignment.spoc_users.all()
                ],
                "approving_admins": [
                    {"id": str(u.id), "username": u.username or u.email, "email": u.email}
                    for u in assignment.approving_admins.all()
                ],
            })

        all_users = [
            {
                "id": str(u.id),
                "username": u.username or u.email,
                "email": u.email,
                "first_name": getattr(u, "first_name", ""),
                "last_name": getattr(u, "last_name", ""),
                "is_superuser": bool(u.is_superuser),
                "is_admin": bool(u.is_admin),
                "platform_role": getattr(u, "platform_role", "user"),
            }
            for u in User.objects.filter(is_active=True).order_by("email")
        ]

        return Response({
            "assignments": results,
            "all_users": all_users,
        })

    def create(self, request):
        domain_id = request.data.get("domain_id")
        spoc_user_ids = request.data.get("spoc_user_ids", [])
        approving_admin_ids = request.data.get("approving_admin_ids", [])

        try:
            domain = IntermediaryFolder.objects.get(id=domain_id, folder_type=IntermediaryFolder.FolderType.DOMAIN)
        except IntermediaryFolder.DoesNotExist:
            return Response({"error": "Domain folder not found"}, status=status.HTTP_404_NOT_FOUND)

        admins = User.objects.filter(id__in=approving_admin_ids)
        invalid_admins = [
            u.email for u in admins
            if not (u.is_admin or u.is_superuser or getattr(u, "platform_role", "") in ["admin", "webadmin", "superadmin"])
        ]
        if invalid_admins:
            return Response(
                {"error": f"Regular users cannot be assigned as Approving Admins: {', '.join(invalid_admins)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment, _ = IntermediaryDomainAssignment.objects.get_or_create(domain_folder=domain)
        assignment.spoc_users.set(User.objects.filter(id__in=spoc_user_ids))
        assignment.approving_admins.set(admins)

        # Dispatch Intermediary Assignment Notifications
        domain_name = domain.name
        nav_url = f"/intermediary-compliance/repository?folder_id={domain.id}"

        for spoc in assignment.spoc_users.all():
            Notification.objects.create(
                user=spoc,
                title=f"Intermediary Assignment (SPOC): {domain_name}",
                message=f"You have been assigned as SPOC for Business Function '{domain_name}'.",
                notification_type=Notification.NotificationType.INTERMEDIARY,
                link_url=nav_url,
                severity="info",
                related_object_type="IntermediaryDomainAssignment",
                related_object_id=str(domain.id),
            )

        for admin in assignment.approving_admins.all():
            Notification.objects.create(
                user=admin,
                title=f"Intermediary Assignment (Reviewer Admin): {domain_name}",
                message=f"You have been assigned as Approving Admin for Business Function '{domain_name}'.",
                notification_type=Notification.NotificationType.INTERMEDIARY,
                link_url=nav_url,
                severity="info",
                related_object_type="IntermediaryDomainAssignment",
                related_object_id=str(domain.id),
            )

        return Response({"message": "Assignments updated successfully"}, status=status.HTTP_200_OK)


class IntermediaryPartnerReportViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = IntermediaryPartnerReport.objects.all()

    def create(self, request, *args, **kwargs):
        partner_folder_id = request.data.get("partner_folder_id")
        title = request.data.get("title")
        compliance_status = request.data.get("compliance_status", IntermediaryPartnerReport.ComplianceStatus.COMPLIANT)
        expiry_date = request.data.get("expiry_date")
        file_path = request.data.get("file_path", "")
        file_obj = request.FILES.get("file")

        try:
            partner_folder = IntermediaryFolder.objects.get(id=partner_folder_id)
        except IntermediaryFolder.DoesNotExist:
            return Response({"error": "Target folder not found"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            # Deactivate previous active reports for this partner folder
            IntermediaryPartnerReport.objects.filter(partner_folder=partner_folder, is_active=True).update(is_active=False)

            report = IntermediaryPartnerReport.objects.create(
                partner_folder=partner_folder,
                title=title,
                file_path=file_path,
                submitted_by=request.user,
                compliance_status=compliance_status,
                approval_status=IntermediaryPartnerReport.ApprovalStatus.PENDING_APPROVAL,
                expiry_date=expiry_date if expiry_date else None,
                is_active=True,
            )

            if file_obj:
                safe_name = f"intermediary_reports/{report.id}_{file_obj.name}"
                saved_path = default_storage.save(safe_name, file_obj)
                report.file_path = f"/api/intermediary-compliance/partner-reports/{report.id}/download/"
                report.save()

            # Notifications to assigned Reviewers, SPOCs, and Superadmins
            domain_folder = partner_folder.parent
            assignment = IntermediaryDomainAssignment.objects.filter(domain_folder=domain_folder).first() if domain_folder else None

            recipients = set()
            if assignment:
                recipients.update(list(assignment.approving_admins.all()))
                recipients.update(list(assignment.spoc_users.all()))
            recipients.update(list(User.objects.filter(Q(is_superuser=True) | Q(is_admin=True))))

            notif_title = "New Partner Report Submitted"
            notif_msg = (
                f"Partner: {partner_folder.name}\n"
                f"Business Function: {domain_folder.name if domain_folder else 'N/A'}\n"
                f"Report: {title}\n"
                f"Submitted by: {request.user.username or request.user.email}\n"
                f"Submitted at: {report.created_at.strftime('%d %b %Y %H:%M')}\n"
                f"Status: Pending Review"
            )
            nav_url = f"/intermediary-compliance/repository?folder_id={partner_folder.id}"

            for r_user in recipients:
                Notification.objects.create(
                    user=r_user,
                    title=notif_title,
                    message=notif_msg,
                    notification_type=Notification.NotificationType.INTERMEDIARY,
                    link_url=nav_url,
                    severity="info",
                    related_object_type="IntermediaryPartnerReport",
                    related_object_id=str(report.id),
                )

        return Response(
            {
                "id": str(report.id),
                "title": report.title,
                "file_path": report.file_path,
                "compliance_status": report.compliance_status,
                "approval_status": report.approval_status,
                "is_active": report.is_active,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        report = self.get_object()
        action_type = request.data.get("action")
        feedback = request.data.get("feedback", "")
        comp_status = request.data.get("compliance_status")
        expiry_date = request.data.get("expiry_date")

        if action_type == "APPROVE":
            report.approval_status = IntermediaryPartnerReport.ApprovalStatus.APPROVED
            report.compliance_status = IntermediaryPartnerReport.ComplianceStatus.COMPLIANT
        elif action_type == "REJECT":
            report.approval_status = IntermediaryPartnerReport.ApprovalStatus.REJECTED
            report.compliance_status = IntermediaryPartnerReport.ComplianceStatus.NON_COMPLIANT
        else:
            return Response({"error": "Invalid action. Use APPROVE or REJECT."}, status=status.HTTP_400_BAD_REQUEST)

        if comp_status:
            report.compliance_status = comp_status

        if expiry_date:
            report.expiry_date = expiry_date

        report.reviewer_feedback = feedback
        report.approved_by = request.user
        report.reviewed_at = timezone.now()
        report.save()

        # Send Review Notification
        domain_folder = report.partner_folder.parent
        assignment = IntermediaryDomainAssignment.objects.filter(domain_folder=domain_folder).first() if domain_folder else None

        recipients = set()
        if assignment:
            recipients.update(list(assignment.spoc_users.all()))
        recipients.update(list(User.objects.filter(Q(is_superuser=True) | Q(is_admin=True))))

        notif_title = f"Report Review {report.approval_status.capitalize()}"
        notif_msg = (
            f"Partner: {report.partner_folder.name}\n"
            f"Business Function: {domain_folder.name if domain_folder else 'N/A'}\n"
            f"Report: {report.title}\n"
            f"Reviewed by: {request.user.username or request.user.email}\n"
            f"Status: {report.approval_status}\n"
            f"Feedback: {feedback or 'None'}"
        )
        nav_url = f"/intermediary-compliance/repository?folder_id={report.partner_folder.id}"

        for r_user in recipients:
            Notification.objects.create(
                user=r_user,
                title=notif_title,
                message=notif_msg,
                notification_type=Notification.NotificationType.INTERMEDIARY,
                link_url=nav_url,
                severity="success" if action_type == "APPROVE" else "error",
                related_object_type="IntermediaryPartnerReport",
                related_object_id=str(report.id),
            )

        return Response({
            "id": str(report.id),
            "approval_status": report.approval_status,
            "compliance_status": report.compliance_status,
            "reviewer_feedback": report.reviewer_feedback,
            "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
        })

    @action(detail=True, methods=["post"], url_path="copy-paste")
    def copy_paste(self, request, pk=None):
        source_report = self.get_object()
        target_partner_id = request.data.get("target_partner_id")
        mode = request.data.get("mode", "COPY").upper()

        if not target_partner_id:
            return Response({"error": "target_partner_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_folder = IntermediaryFolder.objects.get(id=target_partner_id)
            if target_folder.folder_type == IntermediaryFolder.FolderType.PARTNER:
                target_partner = target_folder
            elif target_folder.parent and target_folder.parent.folder_type == IntermediaryFolder.FolderType.PARTNER:
                target_partner = target_folder.parent
            else:
                target_partner = target_folder
        except IntermediaryFolder.DoesNotExist:
            return Response({"error": "Target partner folder not found"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            if mode == "CUT":
                source_report.partner_folder = target_partner
                source_report.save()
                new_report = source_report
            else:
                # COPY mode: duplicate report object
                IntermediaryPartnerReport.objects.filter(partner_folder=target_partner, is_active=True).update(is_active=False)

                new_report = IntermediaryPartnerReport.objects.create(
                    partner_folder=target_partner,
                    title=f"{source_report.title} (Copy)" if source_report.partner_folder == target_partner else source_report.title,
                    file_path=source_report.file_path,
                    submitted_by=request.user,
                    reviewer_feedback=source_report.reviewer_feedback,
                    compliance_status=source_report.compliance_status,
                    approval_status=source_report.approval_status,
                    expiry_date=source_report.expiry_date,
                    is_active=True,
                )

        return Response({
            "id": str(new_report.id),
            "title": new_report.title,
            "file_path": new_report.file_path,
            "compliance_status": new_report.compliance_status,
            "approval_status": new_report.approval_status,
            "expiry_date": str(new_report.expiry_date) if new_report.expiry_date else None,
            "is_active": new_report.is_active,
        }, status=status.HTTP_201_CREATED if mode == "COPY" else status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        report = self.get_object()
        file_path = report.file_path
        if not file_path:
            return Response({"error": "No file attached to this report."}, status=status.HTTP_404_NOT_FOUND)

        # Search storage for file by report id or relative path
        candidates = [
            f"intermediary_reports/{report.id}_{report.title}",
            file_path.replace("/media/", ""),
        ]
        # Also check default storage directory search
        for prefix in ["intermediary_reports/"]:
            try:
                _, files = default_storage.listdir("intermediary_reports")
                for fn in files:
                    if fn.startswith(str(report.id)):
                        candidates.insert(0, f"intermediary_reports/{fn}")
            except Exception:
                pass

        for target in candidates:
            if target and default_storage.exists(target):
                f = default_storage.open(target, "rb")
                filename = target.split("/")[-1].split("_", 1)[-1] if "_" in target.split("/")[-1] else report.title
                response = HttpResponse(f.read(), content_type="application/octet-stream")
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response

        return Response({"error": "File attachment not found on server storage."}, status=status.HTTP_404_NOT_FOUND)


class IntermediaryScopesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        all_domains = IntermediaryFolder.objects.filter(folder_type=IntermediaryFolder.FolderType.DOMAIN).select_related("parent")

        if not is_user_admin(user):
            spoc_domain_ids = set(IntermediaryDomainAssignment.objects.filter(spoc_users=user).values_list("domain_folder_id", flat=True))
            reviewer_domain_ids = set(IntermediaryDomainAssignment.objects.filter(approving_admins=user).values_list("domain_folder_id", flat=True))
            user_domain_ids = spoc_domain_ids | reviewer_domain_ids
            all_domains = all_domains.filter(id__in=user_domain_ids)

        year_ids = set(all_domains.values_list("parent_id", flat=True))
        years = IntermediaryFolder.objects.filter(id__in=year_ids, folder_type=IntermediaryFolder.FolderType.YEAR)

        return Response({
            "full_repository": {"id": "FULL", "name": "Full Repository Scope"},
            "years": [{"id": str(y.id), "name": f"Year {y.name}"} for y in years],
            "business_functions": [
                {"id": str(d.id), "name": f"{d.name} ({d.parent.name if d.parent else 'N/A'})", "year_name": d.parent.name if d.parent else "N/A"}
                for d in all_domains
            ],
        })


class IntermediaryPendingStatusView(APIView):
    authentication_classes = [FlexibleTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        pending_partner_ids = set()
        pending_domain_ids = set()
        pending_year_ids = set()

        is_admin = getattr(user, "is_superuser", False) or getattr(user, "platform_role", "") in ["webadmin", "superadmin"]

        spoc_domain_ids = set(
            IntermediaryDomainAssignment.objects.filter(spoc_users=user).values_list("domain_folder_id", flat=True)
        ) if not is_admin else set()

        if is_admin:
            all_domains = IntermediaryFolder.objects.filter(folder_type=IntermediaryFolder.FolderType.DOMAIN).select_related("parent")
        else:
            all_domains = IntermediaryFolder.objects.filter(id__in=spoc_domain_ids, folder_type=IntermediaryFolder.FolderType.DOMAIN).select_related("parent")

        for df in all_domains:
            child_partners = list(IntermediaryFolder.objects.filter(parent=df, folder_type=IntermediaryFolder.FolderType.PARTNER))
            target_units = child_partners if child_partners else [df]
            for unit in target_units:
                has_approved = IntermediaryPartnerReport.objects.filter(
                    partner_folder=unit,
                    is_active=True,
                    approval_status=IntermediaryPartnerReport.ApprovalStatus.APPROVED
                ).exists()
                if not has_approved:
                    pending_partner_ids.add(str(unit.id))
                    pending_domain_ids.add(str(df.id))
                    if df.parent_id:
                        pending_year_ids.add(str(df.parent_id))

        pending_reports = IntermediaryPartnerReport.objects.filter(
            is_active=True,
            approval_status=IntermediaryPartnerReport.ApprovalStatus.PENDING_APPROVAL,
        ).select_related("partner_folder", "partner_folder__parent", "partner_folder__parent__parent")

        for rep in pending_reports:
            unit = rep.partner_folder
            if unit:
                pending_partner_ids.add(str(unit.id))
                if unit.folder_type == IntermediaryFolder.FolderType.DOMAIN:
                    pending_domain_ids.add(str(unit.id))
                    if unit.parent_id:
                        pending_year_ids.add(str(unit.parent_id))
                elif unit.parent_id:
                    pending_domain_ids.add(str(unit.parent_id))
                    if unit.parent and unit.parent.parent_id:
                        pending_year_ids.add(str(unit.parent.parent_id))

        all_pending_folder_ids = list(pending_partner_ids | pending_domain_ids | pending_year_ids)

        return Response({
            "has_pending_action": len(all_pending_folder_ids) > 0,
            "pending_domain_ids": list(pending_domain_ids),
            "pending_partner_ids": list(pending_partner_ids),
            "pending_year_ids": list(pending_year_ids),
            "pending_folder_ids": all_pending_folder_ids,
        })


class IntermediaryReportGenerationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope_type = request.query_params.get("scope_type", "FULL")
        scope_id = request.query_params.get("scope_id") or request.query_params.get("folder_id")
        summary = get_intermediary_compliance_summary(scope_type=scope_type, scope_id=scope_id, user=request.user)
        return Response(summary)


class IntermediaryReportPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        scope_type = request.data.get("scope_type", "FULL")
        scope_id = request.data.get("scope_id")

        summary = get_intermediary_compliance_summary(scope_type=scope_type, scope_id=scope_id, user=request.user)

        from core.models import CustomReportTemplate
        custom_tmpl = CustomReportTemplate.objects.filter(report_type="intermediary_compliance", is_active=True).first()

        if custom_tmpl:
            custom_title = custom_tmpl.title or "INTERMEDIARY COMPLIANCE REPORT"
            custom_header = custom_tmpl.header_text or "CONFIDENTIAL - FOR INTERNAL USE ONLY"
            custom_footer = custom_tmpl.footer_text or "Enterprise Compliance Platform"
            custom_company = custom_tmpl.company_name or "Enterprise Compliance Organization"
            primary_color = custom_tmpl.primary_color or "#3b82f6"
            show_exec_summary = custom_tmpl.show_executive_summary
            show_findings = custom_tmpl.show_findings
            show_evidence = custom_tmpl.show_evidence_details
            show_activity = custom_tmpl.show_activity_history
            custom_exec_text = custom_tmpl.custom_executive_summary_text or ""
            custom_concluding_text = custom_tmpl.custom_concluding_notes or ""
            custom_findings_t = custom_tmpl.custom_findings_title or "4. Non-Compliant & At-Risk Entities"
            custom_evidence_t = custom_tmpl.custom_evidence_title or "3. Partner Compliance Statuses"
            custom_activity_t = custom_tmpl.custom_activity_title or "5. Formal Sign-Off"
        else:
            custom_title = "INTERMEDIARY COMPLIANCE REPORT"
            custom_header = "CONFIDENTIAL - FOR INTERNAL USE ONLY"
            custom_footer = "Enterprise Compliance Platform"
            custom_company = "Enterprise Compliance Organization"
            primary_color = "#3b82f6"
            show_exec_summary = True
            show_findings = True
            show_evidence = True
            show_activity = True
            custom_exec_text = ""
            custom_concluding_text = ""
            custom_findings_t = "4. Non-Compliant & At-Risk Entities"
            custom_evidence_t = "3. Partner Compliance Statuses"
            custom_activity_t = "5. Formal Sign-Off"

        from core.notification_service import _get_logo_base64
        logo_b64 = _get_logo_base64(theme="light")
        logo_img_tag = (
            f'<img src="data:image/svg+xml;base64,{logo_b64}" style="max-height: 75px; max-width: 280px; width: auto; margin-bottom: 15px; display: block; margin-left: auto; margin-right: auto;" />'
            if logo_b64
            else f'<div style="font-size: 14pt; text-transform: uppercase; letter-spacing: 2px; color: {primary_color}; font-weight: bold; margin-bottom: 20px;">{custom_company}</div>'
        )

        exec_summary_html = ""
        if show_exec_summary:
            exec_note_html = f'<div style="background: #f0f4ff; border-left: 4px solid {primary_color}; padding: 10px; margin-bottom: 15px; font-size: 9.5pt;"><strong>Executive Note:</strong> {custom_exec_text}</div>' if custom_exec_text else ''
            exec_summary_html = f"""
            <div class="section-header">1. Executive Summary</div>
            {exec_note_html}
            <p>This official compliance audit report summarizes the current active third-party report statuses across authorized Business Functions and Partners for <strong>{summary['target_name']}</strong>.</p>
            <div class="grid">
                <div class="card"><div class="card-val" style="color: {primary_color};">{summary['total_assigned']}</div><div class="card-lbl">Total Assigned</div></div>
                <div class="card"><div class="card-val" style="color: #64748b;">{summary['pending_evidence_count']}</div><div class="card-lbl">Pending Evidence</div></div>
                <div class="card"><div class="card-val" style="color: #ca8a04;">{summary['under_review_count']}</div><div class="card-lbl">Under Review</div></div>
                <div class="card"><div class="card-val" style="color: #16a34a;">{summary['approved_count']}</div><div class="card-lbl">Approved</div></div>
                <div class="card"><div class="card-val" style="color: #dc2626;">{summary['rejected_count']}</div><div class="card-lbl">Rejected</div></div>
                <div class="card"><div class="card-val" style="color: {primary_color};">{summary['approved_compliance_rate']}%</div><div class="card-lbl">Approved Rate</div></div>
                <div class="card"><div class="card-val" style="color: #0284c7;">{summary['compliance_coverage']}%</div><div class="card-lbl">Coverage Rate</div></div>
            </div>
            """

        evidence_section_html = ""
        if show_evidence:
            evidence_section_html = f"""
            <div class="section-header">{custom_evidence_t}</div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Partner</th>
                        <th>Business Function</th>
                        <th>Status</th>
                        <th>SPOC</th>
                        <th>Reviewer</th>
                        <th>Last Submitted</th>
                        <th>Last Reviewed</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([f"<tr><td>{p['partner_name']}</td><td>{p['domain_name']}</td><td>{p['status']}</td><td>{p['spoc']}</td><td>{p['reviewer']}</td><td>{p['last_submitted'] or '--'}</td><td>{p['last_reviewed'] or '--'}</td></tr>" for p in summary['partner_breakdown']])}
                </tbody>
            </table>
            """

        findings_section_html = ""
        if show_findings:
            findings_section_html = f"""
            <div class="section-header">{custom_findings_t}</div>
            <p><strong>Partners Requiring Action ({len(summary['non_compliant_partners'])}):</strong></p>
            <ul>
                {"".join([f"<li><strong>{p['partner_name']}</strong> ({p['domain_name']}) &mdash; <span class='badge-rejected'>{p['status']}</span> (SPOC: {p['spoc']} | Reviewer: {p['reviewer']})</li>" for p in summary['non_compliant_partners']]) if summary['non_compliant_partners'] else "<li>All partner requirements are compliant.</li>"}
            </ul>
            """

        signoff_section_html = ""
        if show_activity:
            concluding_note_html = f'<p style="font-size: 9.5pt; color: #475569; margin-bottom: 15px;"><strong>Concluding Notes:</strong> {custom_concluding_text}</p>' if custom_concluding_text else ''
            signoff_section_html = f"""
            <div class="sign-block">
                <div class="section-header">{custom_activity_t}</div>
                {concluding_note_html}
                <div class="sign-row">
                    <div class="sign-col"><br>________________________<br>Prepared By (SPOC)</div>
                    <div class="sign-col"><br>________________________<br>Reviewed By (Reviewer)</div>
                    <div class="sign-col"><br>________________________<br>Approved By (CISO / Management)</div>
                </div>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{custom_title}</title>
            <style>
                @page {{
                    size: A4 portrait;
                    margin: 20mm 15mm 20mm 15mm;
                    @top-left {{
                        content: "{custom_header}";
                        font-size: 8pt;
                        font-family: Helvetica, Arial, sans-serif;
                        color: #64748b;
                    }}
                    @top-right {{
                        content: "{summary['target_name']} | {custom_title}";
                        font-size: 8pt;
                        font-family: Helvetica, Arial, sans-serif;
                        color: #64748b;
                    }}
                    @bottom-left {{
                        content: "{custom_footer} | Generated: {datetime.now().strftime('%d %B %Y %H:%M')}";
                        font-size: 8pt;
                        font-family: Helvetica, Arial, sans-serif;
                        color: #64748b;
                    }}
                    @bottom-right {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 8pt;
                        font-weight: bold;
                        font-family: Helvetica, Arial, sans-serif;
                        color: #0f172a;
                    }}
                }}
                @page:first {{
                    margin: 0;
                    @top-left {{ content: none; }}
                    @top-right {{ content: none; }}
                    @bottom-left {{ content: none; }}
                    @bottom-right {{ content: none; }}
                }}
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 10pt; color: #1e293b; line-height: 1.5; }}
                .cover-page {{
                    height: 100vh;
                    padding: 25mm 20mm 20mm 20mm;
                    box-sizing: border-box;
                    background: #ffffff;
                    color: #1e293b;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    page-break-after: always;
                }}
                .cover-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding-bottom: 12px;
                    border-bottom: 1px solid #e2e8f0;
                    font-size: 8.5pt;
                    color: #64748b;
                    font-family: monospace;
                }}
                .cover-title-card {{
                    margin-top: 25px;
                    margin-bottom: 20px;
                    padding: 22px 20px;
                    border-radius: 10px;
                    background-color: rgba(99, 102, 241, 0.06);
                    border-left: 5px solid {primary_color};
                }}
                .cover-brand {{
                    font-size: 9.5pt;
                    font-weight: 800;
                    letter-spacing: 2px;
                    color: #64748b;
                    text-transform: uppercase;
                    margin-bottom: 6px;
                }}
                .cover-title {{
                    font-size: 22pt;
                    font-weight: 800;
                    line-height: 1.2;
                    color: {primary_color};
                    margin-bottom: 6px;
                }}
                .cover-subtitle {{
                    font-size: 11pt;
                    color: #475569;
                    font-weight: 500;
                }}
                .cover-exec-card {{
                    margin-top: 15px;
                    padding: 14px 18px;
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }}
                .cover-exec-title {{
                    font-size: 8pt;
                    text-transform: uppercase;
                    font-weight: bold;
                    color: #64748b;
                    letter-spacing: 0.5px;
                    margin-bottom: 4px;
                }}
                .cover-exec-text {{
                    font-size: 9pt;
                    color: #334155;
                    line-height: 1.45;
                }}
                .cover-score-card {{
                    margin-top: 15px;
                    padding: 14px 18px;
                    background: #eef2ff;
                    border: 1px solid #c7d2fe;
                    border-radius: 8px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .cover-score-label {{
                    font-weight: bold;
                    color: #1e293b;
                    font-size: 10pt;
                }}
                .cover-score-sub {{
                    font-size: 8pt;
                    color: #64748b;
                    margin-top: 2px;
                }}
                .cover-score-badge {{
                    background-color: {primary_color};
                    color: #ffffff;
                    padding: 6px 14px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 10.5pt;
                }}
                .cover-meta-grid {{
                    margin-top: 20px;
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 10px;
                    background: #f8fafc;
                    padding: 15px;
                    border-radius: 10px;
                    border: 1px solid #e2e8f0;
                }}
                .cover-meta-item {{
                    font-size: 9pt;
                }}
                .cover-meta-label {{
                    color: #64748b;
                    font-size: 7.5pt;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    font-weight: 600;
                }}
                .cover-meta-val {{
                    color: #0f172a;
                    font-weight: 600;
                    margin-top: 2px;
                }}
                .cover-footer {{
                    margin-top: auto;
                    padding-top: 15px;
                    border-top: 1px solid #e2e8f0;
                    display: flex;
                    justify-content: space-between;
                    font-size: 8.5pt;
                    color: #64748b;
                    font-family: monospace;
                }}
                .section-header {{ font-size: 14pt; font-weight: bold; color: #0f172a; border-bottom: 2px solid {primary_color}; padding-bottom: 4px; margin-top: 25px; margin-bottom: 12px; page-break-after: avoid; }}
                .grid {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
                .card {{ flex: 1; min-width: 120px; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; text-align: center; }}
                .card-val {{ font-size: 18pt; font-weight: bold; color: {primary_color}; }}
                .card-lbl {{ font-size: 8pt; text-transform: uppercase; color: #64748b; font-weight: bold; margin-top: 4px; }}
                table.data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 9pt; }}
                table.data-table th, table.data-table td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }}
                table.data-table th {{ background-color: #0f172a; font-weight: bold; color: #ffffff; }}
                .badge-approved {{ color: #166534; font-weight: bold; }}
                .badge-rejected {{ color: #991b1b; font-weight: bold; }}
                .badge-review {{ color: #854d0e; font-weight: bold; }}
                .badge-pending {{ color: #475569; font-weight: bold; }}
                .sign-block {{ margin-top: 40px; page-break-inside: avoid; }}
                .sign-row {{ display: flex; justify-content: space-between; margin-top: 30px; }}
                .sign-col {{ width: 30%; border-top: 1px solid #000; padding-top: 8px; text-align: center; font-size: 9pt; }}
            </style>
        </head>
        <body>
            <div class="cover-page">
                <div>
                    <div class="cover-header">
                        <span>{custom_header}</span>
                        <span style="font-weight: bold; color: {primary_color};">Page 1</span>
                    </div>

                    <div style="margin-top: 15px;">
                        {logo_img_tag}
                    </div>

                    <div class="cover-title-card" style="background-color: {primary_color}10; border-left: 5px solid {primary_color};">
                        <div class="cover-brand">{custom_company}</div>
                        <div class="cover-title" style="color: {primary_color};">{custom_title}</div>
                        <div class="cover-subtitle">Executive Compliance Summary Dossier &bull; {summary['target_name']}</div>
                    </div>

                    {f'<div class="cover-exec-card"><div class="cover-exec-title">Executive Overview</div><div class="cover-exec-text">{custom_exec_text}</div></div>' if custom_exec_text else ''}

                    <div class="cover-score-card">
                        <div>
                            <div class="cover-score-label">Overall Compliance Score</div>
                            <div class="cover-score-sub">Based on active partner control evaluation and evidence review</div>
                        </div>
                        <div class="cover-score-badge" style="background-color: {primary_color};">
                            {summary['approved_compliance_rate']}% COMPLIANT
                        </div>
                    </div>

                    <div class="cover-meta-grid">
                        <div class="cover-meta-item">
                            <div class="cover-meta-label">Scope Target</div>
                            <div class="cover-meta-val">{summary['target_name']}</div>
                        </div>
                        <div class="cover-meta-item">
                            <div class="cover-meta-label">Reporting Period</div>
                            <div class="cover-meta-val">{summary['reporting_period']}</div>
                        </div>
                        <div class="cover-meta-item">
                            <div class="cover-meta-label">Date Generated</div>
                            <div class="cover-meta-val">{datetime.now().strftime('%d %B %Y %H:%M')}</div>
                        </div>
                        <div class="cover-meta-item">
                            <div class="cover-meta-label">Generated By</div>
                            <div class="cover-meta-val">{request.user.email}</div>
                        </div>
                        <div class="cover-meta-item">
                            <div class="cover-meta-label">Total Assigned</div>
                            <div class="cover-meta-val">{summary['total_assigned']}</div>
                        </div>
                        <div class="cover-meta-item">
                            <div class="cover-meta-label">Classification</div>
                            <div class="cover-meta-val">{custom_header}</div>
                        </div>
                    </div>
                </div>

                <div class="cover-footer">
                    <div>{custom_footer}</div>
                    <div>{datetime.now().strftime('%d %B %Y %H:%M')}</div>
                </div>
            </div>

            {exec_summary_html}

            <div class="section-header">2. Business Function Breakdown</div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Business Function</th>
                        <th>Year</th>
                        <th>Assigned</th>
                        <th>Pending Evidence</th>
                        <th>Under Review</th>
                        <th>Approved</th>
                        <th>Rejected</th>
                        <th>Approved Rate (%)</th>
                        <th>Coverage (%)</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([f"<tr><td>{b['domain_name']}</td><td>{b['year_name']}</td><td>{b['total_assigned']}</td><td>{b['pending_evidence']}</td><td>{b['under_review']}</td><td class='badge-approved'>{b['approved']}</td><td class='badge-rejected'>{b['rejected']}</td><td>{b['compliance_rate']}%</td><td>{b['coverage']}%</td></tr>" for b in summary['business_function_breakdown']])}
                </tbody>
            </table>

            {evidence_section_html}

            {findings_section_html}

            {signoff_section_html}
        </body>
        </html>
        """

        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        safe_target_name = str(summary.get("target_name", "Scope")).replace(" ", "_")
        response["Content-Disposition"] = f'inline; filename="intermediary_compliance_report_{safe_target_name}.pdf"'
        return response
        filename = f"Intermediary_Compliance_{summary['scope_type']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        gen_report = IntermediaryGeneratedReport.objects.create(
            title=f"Intermediary Compliance Report - {summary['target_name']}",
            scope_type=summary['scope_type'],
            scope_name=summary['target_name'],
            scope_id=summary['scope_id'],
            reporting_period=summary['reporting_period'],
            metrics_snapshot={
                "total_assigned": summary['total_assigned'],
                "pending_evidence_count": summary['pending_evidence_count'],
                "under_review_count": summary['under_review_count'],
                "approved_count": summary['approved_count'],
                "rejected_count": summary['rejected_count'],
                "approved_compliance_rate": summary['approved_compliance_rate'],
                "compliance_coverage": summary['compliance_coverage'],
            },
            generated_by=request.user,
        )
        gen_report.file.save(filename, ContentFile(pdf_bytes), save=True)

        # Dispatch Notification for Summary Report Generation
        recipients = set(User.objects.filter(Q(is_superuser=True) | Q(is_admin=True) | Q(platform_role__in=["superadmin", "webadmin", "admin"])))
        notif_title = f"Intermediary Report Generated: {summary['target_name']}"
        notif_msg = (
            f"An Intermediary Compliance Executive Summary report was generated for '{summary['target_name']}'.\n"
            f"Coverage: {summary['compliance_coverage']}%\n"
            f"Generated by: {request.user.username or request.user.email}"
        )
        nav_url = "/intermediary-compliance/reports"

        for r_user in recipients:
            Notification.objects.create(
                user=r_user,
                title=notif_title,
                message=notif_msg,
                notification_type=Notification.NotificationType.INTERMEDIARY,
                link_url=nav_url,
                severity="info",
                related_object_type="IntermediaryGeneratedReport",
                related_object_id=str(gen_report.id),
            )

        res = HttpResponse(pdf_bytes, content_type="application/pdf")
        res["Content-Disposition"] = f'attachment; filename="{filename}"'
        return res


class IntermediaryGeneratedReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = IntermediaryGeneratedReport.objects.all()

    def list(self, request):
        reports = self.get_queryset()
        return Response([
            {
                "id": str(r.id),
                "title": r.title,
                "scope_type": r.scope_type,
                "scope_name": r.scope_name,
                "reporting_period": r.reporting_period,
                "generated_by": r.generated_by.email if r.generated_by else "System",
                "created_at": r.created_at.strftime("%d %b %Y %H:%M") if r.created_at else None,
                "file_url": r.file.url if r.file else None,
            }
            for r in reports
        ])

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        report = self.get_object()
        if not report.file:
            return Response({"error": "PDF file not found"}, status=status.HTTP_404_NOT_FOUND)

        pdf_bytes = report.file.read()
        res = HttpResponse(pdf_bytes, content_type="application/pdf")
        res["Content-Disposition"] = f'attachment; filename="{report.title}.pdf"'
        return res

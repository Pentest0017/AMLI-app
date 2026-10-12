import datetime
from django.utils import timezone
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from core.models import ControlAssignment, User, AuditEvidenceLink
from core.escalation_engine import compute_current_escalation_level


class DefaultersTrackerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        is_admin = getattr(user, 'is_superuser', False) or getattr(user, 'platform_role', '') in ['superadmin', 'webadmin', 'admin']

        qs = ControlAssignment.objects.filter(
            is_active=True,
            spoc_user__isnull=False
        ).select_related('requirement_node', 'framework', 'spoc_user', 'spoc_user__reports_to')

        if not is_admin:
            subordinate_ids = set(user.direct_reports.values_list('id', flat=True))
            subordinate_ids.add(user.id)
            qs = qs.filter(spoc_user_id__in=subordinate_ids)

        spoc_id = request.query_params.get('spoc_id')
        framework_id = request.query_params.get('framework_id')
        level_filter = request.query_params.get('escalation_level')

        if spoc_id:
            qs = qs.filter(spoc_user_id=spoc_id)
        if framework_id:
            qs = qs.filter(framework_id=framework_id)
        if level_filter:
            qs = qs.filter(escalation_level=level_filter)

        ca_list = list(qs)
        ca_ids = [ca.id for ca in ca_list]

        # Batch load active cleared evidence links for instant O(1) in-memory checking
        cleared_ca_ids = set(
            AuditEvidenceLink.objects.filter(
                is_active=True,
                control_evidence_mapping__control_assignment_id__in=ca_ids,
                review_status__in=["SUBMITTED", "PENDING_REVIEW", "APPROVED"]
            ).values_list('control_evidence_mapping__control_assignment_id', flat=True)
        ) | set(
            AuditEvidenceLink.objects.filter(
                is_active=True,
                assessment_control__control_assignment_id__in=ca_ids,
                review_status__in=["SUBMITTED", "PENDING_REVIEW", "APPROVED"]
            ).values_list('assessment_control__control_assignment_id', flat=True)
        )

        results = []
        for ca in ca_list:
            cleared = ca.is_not_applicable or (ca.id in cleared_ca_ids)

            active_deadline = ca.l3_final_deadline or ca.l2_grace_deadline or ca.due_date
            days_overdue = 0
            if not cleared and active_deadline and active_deadline < today:
                days_overdue = (today - active_deadline).days

            current_level = compute_current_escalation_level(ca, today)
            if not cleared and days_overdue == 0 and current_level == 'ASSIGNED':
                continue

            spoc_email = ca.spoc_user.email if ca.spoc_user else 'N/A'
            spoc_name = f'{ca.spoc_user.first_name} {ca.spoc_user.last_name}'.strip() if ca.spoc_user else spoc_email
            supervisor = ca.spoc_user.reports_to if ca.spoc_user else None
            sup_email = supervisor.email if supervisor else 'Webadmin'

            results.append({
                'id': str(ca.id),
                'spoc_email': spoc_email,
                'spoc_name': spoc_name,
                'supervisor_email': sup_email,
                'control_ref_id': ca.requirement_node.ref_id if ca.requirement_node else 'N/A',
                'control_title': ca.requirement_node.name if ca.requirement_node else 'Control',
                'framework_name': ca.framework.name if ca.framework else 'Library',
                'assignment_date': ca.created_at.strftime('%Y-%m-%d') if ca.created_at else 'N/A',
                'original_due_date': ca.due_date.strftime('%Y-%m-%d') if ca.due_date else 'N/A',
                'l1_reminder_date': ca.l1_reminder_date.strftime('%Y-%m-%d') if ca.l1_reminder_date else None,
                'l2_grace_deadline': ca.l2_grace_deadline.strftime('%Y-%m-%d') if ca.l2_grace_deadline else None,
                'l3_final_deadline': ca.l3_final_deadline.strftime('%Y-%m-%d') if ca.l3_final_deadline else None,
                'active_deadline': active_deadline.strftime('%Y-%m-%d') if active_deadline else 'N/A',
                'escalation_level': 'CLEARED' if cleared else current_level,
                'is_cleared': cleared,
                'days_overdue': days_overdue,
            })

        return Response({
            'count': len(results),
            'results': results,
        })

import time
import threading
import datetime
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from core.models import (
    EscalationRule,
    EscalationLog,
    ComplianceAssessment,
    ControlAssignment,
    Evidence,
    User,
    AuditEvidenceLink,
)
from core.notification_service import (
    NotificationService,
    render_custom_or_default_template,
    render_official_html_email,
)

_worker_thread = None
_worker_running = False


def log_escalation_audit_entry(assignment, recipient_user, step_label, trigger_type, actor=None):
    try:
        from auditlog.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        ref_id = assignment.requirement_node.ref_id if (assignment and assignment.requirement_node) else 'N/A'
        recip_email = recipient_user.email if recipient_user else 'N/A'

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(assignment) if assignment else None,
            object_pk=str(assignment.id) if assignment else str(recipient_user.id if recipient_user else '0'),
            object_repr=f'Escalation Email ({step_label}) sent to {recip_email} for Control {ref_id}',
            action=1,
            actor=actor,
            changes={
                'escalation_notice': ['N/A', f'Sent to {recip_email}'],
                'control_ref_id': [ref_id, ref_id],
                'step_label': [step_label, step_label],
                'trigger_type': [trigger_type, trigger_type],
            },
        )
    except Exception as log_err:
        print(f'LogEntry recording warning: {log_err}')

    try:
        from core.models import AssignmentChangeLog
        if assignment:
            recip_email = recipient_user.email if recipient_user else 'N/A'
            AssignmentChangeLog.objects.create(
                control_assignment=assignment,
                action_type='MODIFIED',
                field_changed='escalation_sent',
                reason=f'Escalation email ({step_label}) sent to {recip_email}',
                changed_by=actor,
            )
    except Exception as ac_err:
        print(f'AssignmentChangeLog recording warning: {ac_err}')


def resolve_escalation_recipients(spoc_user, level: str) -> list:
    if not spoc_user:
        return []

    recipients_dict = {spoc_user.id: spoc_user}
    supervisor = spoc_user.reports_to

    if level == 'L1':
        return list(recipients_dict.values())

    if level == 'L2':
        if supervisor:
            recipients_dict[supervisor.id] = supervisor
        return list(recipients_dict.values())

    if level == 'L3':
        if supervisor:
            recipients_dict[supervisor.id] = supervisor
            second_supervisor = supervisor.reports_to
            if second_supervisor:
                recipients_dict[second_supervisor.id] = second_supervisor
            else:
                webadmins = User.objects.filter(
                    Q(is_superuser=True) | Q(platform_role='superadmin') | Q(platform_role='webadmin')
                ).exclude(id__in=recipients_dict.keys())
                for wa in webadmins:
                    recipients_dict[wa.id] = wa
        else:
            webadmins = User.objects.filter(
                Q(is_superuser=True) | Q(platform_role='superadmin') | Q(platform_role='webadmin')
            ).exclude(id__in=recipients_dict.keys())
            for wa in webadmins:
                recipients_dict[wa.id] = wa

    return list(recipients_dict.values())


def is_assignment_cleared(assignment: ControlAssignment) -> bool:
    if not assignment:
        return False

    if assignment.is_not_applicable:
        return True

    from core.models import AuditEvidenceLink
    from django.db.models import Q

    active_link = AuditEvidenceLink.objects.filter(
        Q(assessment_control__control_assignment=assignment) | Q(control_evidence_mapping__control_assignment=assignment),
        is_active=True
    ).first()

    if active_link:
        review_st = (active_link.review_status or "").upper()
        if review_st in ["SUBMITTED", "PENDING_REVIEW", "APPROVED"]:
            return True
        if active_link.evidence:
            ev_st = str(active_link.evidence.status).lower()
            if ev_st in ["approved", "compliant", "done", "submitted", "pending"]:
                return True

    return False


def compute_current_escalation_level(assignment: ControlAssignment, now=None) -> str:
    """
    Authoritative single-source helper to compute the current real-time escalation level tag
    based on evidence clearance status, today's date, configured deadlines, and sent escalation logs.
    """
    if not assignment:
        return "ASSIGNED"

    if is_assignment_cleared(assignment):
        return "CLEARED"

    if now is None:
        today = timezone.now().date()
    else:
        today = now.date() if isinstance(now, datetime.datetime) else now

    from core.models import EscalationLog
    sent_levels = set(
        EscalationLog.objects.filter(
            control_assignment=assignment, email_sent=True
        ).values_list('step_label', flat=True)
    )

    if 'L3' in sent_levels and assignment.l3_final_deadline and today > assignment.l3_final_deadline:
        return "FINAL_DEFAULTER"
    if assignment.l3_final_deadline and today > assignment.l3_final_deadline:
        return "FINAL_DEFAULTER"

    if 'L3' in sent_levels or (assignment.l3_final_deadline and today >= assignment.l3_final_deadline):
        return "L3_FINAL_GRACE"
    if 'L2' in sent_levels or (assignment.l2_grace_deadline and today >= assignment.l2_grace_deadline):
        return "L2_GRACE"
    if 'L1' in sent_levels or (assignment.l1_reminder_date and today >= assignment.l1_reminder_date):
        return "L1"

    return "ASSIGNED"


def schedule_escalation_level(assignment: ControlAssignment, level: str, target_date, actor=None):
    if not assignment:
        return

    if level == 'L1':
        assignment.l1_reminder_date = target_date
    elif level == 'L2':
        assignment.l2_grace_deadline = target_date
    elif level == 'L3':
        assignment.l3_final_deadline = target_date

    assignment.escalation_level = compute_current_escalation_level(assignment)
    assignment.save(update_fields=['l1_reminder_date', 'l2_grace_deadline', 'l3_final_deadline', 'escalation_level'])


def process_automated_escalations(now=None):
    if now is None:
        now = timezone.now()
    today = now.date() if isinstance(now, datetime.datetime) else now

    assignments = ControlAssignment.objects.filter(
        is_active=True,
        spoc_user__isnull=False
    ).select_related('requirement_node', 'framework', 'spoc_user', 'spoc_user__reports_to')

    processed_count = 0

    for ca in assignments:
        if is_assignment_cleared(ca):
            if ca.escalation_level not in ['ASSIGNED', 'CLEARED']:
                ca.escalation_level = 'CLEARED'
                ca.save(update_fields=['escalation_level'])
            continue

        stages_to_check = []
        if ca.l1_reminder_date and ca.l1_reminder_date <= today:
            stages_to_check.append(('L1', ca.l1_reminder_date, 'escalation_l1'))
        if ca.l2_grace_deadline and ca.l2_grace_deadline <= today:
            stages_to_check.append(('L2', ca.l2_grace_deadline, 'escalation_l2'))
        if ca.l3_final_deadline and ca.l3_final_deadline <= today:
            stages_to_check.append(('L3', ca.l3_final_deadline, 'escalation_l3'))

        for step_label, target_date, tmpl_key in stages_to_check:
            # Check idempotency: skip if already sent for this assignment & date
            already_sent = EscalationLog.objects.filter(
                control_assignment=ca,
                step_label=step_label,
                escalation_date=target_date,
                email_sent=True,
            ).exists()

            if already_sent:
                continue

            recipients = resolve_escalation_recipients(ca.spoc_user, step_label)
            if not recipients:
                continue

            ref_id = ca.requirement_node.ref_id if ca.requirement_node else 'N/A'
            title = ca.requirement_node.name if ca.requirement_node else 'Control'
            fw_name = ca.framework.name if ca.framework else 'Library'
            due_str = ca.due_date.strftime('%Y-%m-%d') if ca.due_date else 'N/A'

            controls_text = f'• [{ref_id}] {title} (Framework: {fw_name}) - Original Due Date: {due_str}'
            base_url = getattr(settings, 'CISO_ASSISTANT_URL', 'https://localhost:8443')
            action_url = f'{base_url}/compliance/evidences'

            spoc_name = ca.spoc_user.first_name or ca.spoc_user.email.split('@')[0]
            supervisor_name = (ca.spoc_user.reports_to.first_name or ca.spoc_user.reports_to.email.split('@')[0]) if ca.spoc_user.reports_to else 'Webadmin'

            tmpl_vars = {
                'spoc_name': spoc_name,
                'supervisor_name': supervisor_name,
                'controls_list': controls_text,
                'due_date': due_str,
                'l2_deadline': ca.l2_grace_deadline.strftime('%Y-%m-%d') if ca.l2_grace_deadline else due_str,
                'l3_deadline': ca.l3_final_deadline.strftime('%Y-%m-%d') if ca.l3_final_deadline else due_str,
                'action_url': action_url,
            }

            subject, body = render_custom_or_default_template(tmpl_key, tmpl_vars)

            for user_recip in recipients:
                notif = NotificationService.notify(
                    user=user_recip,
                    title=subject,
                    message=body,
                    notification_type='ESCALATION',
                    link_url='/compliance/evidences',
                    send_email=True,
                    related_object_type='ControlAssignment',
                    related_object_id=str(ca.id),
                    event_id=f'escalation_{ca.id}_{step_label}_{target_date}_{user_recip.id}',
                )

                EscalationLog.objects.create(
                    control_assignment=ca,
                    trigger_type=EscalationLog.TriggerType.AUTOMATIC,
                    recipient_user=user_recip,
                    recipient_email=user_recip.email,
                    email_sent=True,
                    step_label=step_label,
                    escalation_date=target_date,
                )

                log_escalation_audit_entry(ca, user_recip, step_label, 'AUTOMATIC')
                processed_count += 1

        ca.escalation_level = compute_current_escalation_level(ca, today)
        ca.save(update_fields=['escalation_level'])

    return processed_count


def start_escalation_worker():
    import threading
    global _worker_running, _worker_thread
    if _worker_running:
        return

    def _worker_loop():
        global _worker_running
        _worker_running = True
        print('[EscalationEngine] Automated escalation background worker started.')
        while _worker_running:
            try:
                process_automated_escalations()
                from core.assignment_batching import process_pending_assignment_batches
                process_pending_assignment_batches()
            except Exception as err:
                print(f'[EscalationEngine] Worker loop exception: {err}')
            time.sleep(300)

    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def start_escalation_background_worker():
    start_escalation_worker()

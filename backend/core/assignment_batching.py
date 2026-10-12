import uuid
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from core.models import AssignmentBatch, AssignmentBatchItem, ControlAssignment, User
from core.notification_service import NotificationService, render_custom_or_default_template, render_official_html_email
from global_settings.models import GlobalSettings


def get_configured_batching_window_hours() -> int:
    try:
        setting = GlobalSettings.objects.filter(name='assignment_batching').first()
        if setting and isinstance(setting.value, dict):
            return int(setting.value.get('window_hours', 4))
    except Exception:
        pass
    return 4


def set_configured_batching_window_hours(hours: int):
    setting, _ = GlobalSettings.objects.get_or_create(name='assignment_batching')
    val = setting.value if isinstance(setting.value, dict) else {}
    val['window_hours'] = max(1, min(168, int(hours)))
    setting.value = val
    setting.save()


def queue_control_assignment(assignment: ControlAssignment):
    if not assignment or not assignment.spoc_user:
        return

    now = timezone.now()
    window_hours = get_configured_batching_window_hours()

    with transaction.atomic():
        open_batch = AssignmentBatch.objects.filter(
            spoc_user=assignment.spoc_user,
            status=AssignmentBatch.Status.OPEN,
            window_expires_at__gt=now
        ).select_for_update().first()

        if not open_batch:
            expires_at = now + timedelta(hours=window_hours)
            event_id = f'batch_{assignment.spoc_user.id}_{int(expires_at.timestamp())}_{uuid.uuid4().hex[:8]}'
            open_batch = AssignmentBatch.objects.create(
                event_id=event_id,
                spoc_user=assignment.spoc_user,
                status=AssignmentBatch.Status.OPEN,
                window_expires_at=expires_at,
            )

        AssignmentBatchItem.objects.get_or_create(
            batch=open_batch,
            control_assignment=assignment
        )
        assignment.pending_email_notification = True
        assignment.save(update_fields=['pending_email_notification'])


def process_pending_assignment_batches():
    now = timezone.now()
    expired_batches = AssignmentBatch.objects.filter(
        status=AssignmentBatch.Status.OPEN,
        window_expires_at__lte=now
    ).select_related('spoc_user')

    dispatched_count = 0
    for batch in expired_batches:
        with transaction.atomic():
            batch_ref = AssignmentBatch.objects.select_for_update().filter(id=batch.id, status=AssignmentBatch.Status.OPEN).first()
            if not batch_ref:
                continue

            items = list(AssignmentBatchItem.objects.filter(batch=batch_ref).select_related(
                'control_assignment__requirement_node', 'control_assignment__framework'
            ))

            if not items:
                batch_ref.status = AssignmentBatch.Status.DISPATCHED
                batch_ref.dispatched_at = now
                batch_ref.save()
                continue

            controls_lines = []
            primary_due_date = 'No Due Date'
            for item in items:
                ca = item.control_assignment
                ref_id = ca.requirement_node.ref_id if ca.requirement_node else 'N/A'
                title = ca.requirement_node.name if ca.requirement_node else 'Control'
                fw_name = ca.framework.name if ca.framework else 'Library'
                due_str = ca.due_date.strftime('%Y-%m-%d') if ca.due_date else 'No Due Date'
                if primary_due_date == 'No Due Date' and ca.due_date:
                    primary_due_date = ca.due_date.strftime('%Y-%m-%d')
                controls_lines.append(f'• [{ref_id}] {title} (Framework: {fw_name}) - Original Due Date: {due_str}')

            controls_list_text = '\n'.join(controls_lines)
            base_url = getattr(settings, 'CISO_ASSISTANT_URL', 'https://localhost:8443')
            action_url = f'{base_url}/compliance/evidences'

            spoc_name = batch_ref.spoc_user.first_name or batch_ref.spoc_user.email.split('@')[0]
            template_vars = {
                'spoc_name': spoc_name,
                'controls_list': controls_list_text,
                'due_date': primary_due_date,
                'total_controls': str(len(items)),
                'action_url': action_url,
            }

            subject, body = render_custom_or_default_template('control_assignment', template_vars)

            NotificationService.notify(
                user=batch_ref.spoc_user,
                title=subject,
                message=body,
                notification_type='CONTROL_ASSIGNMENT',
                link_url='/compliance/evidences',
                send_email=True,
                related_object_type='AssignmentBatch',
                related_object_id=str(batch_ref.id),
                event_id=batch_ref.event_id,
            )

            batch_ref.status = AssignmentBatch.Status.DISPATCHED
            batch_ref.dispatched_at = now
            batch_ref.save()

            for item in items:
                ca = item.control_assignment
                ca.pending_email_notification = False
                ca.save(update_fields=['pending_email_notification'])

            dispatched_count += 1

    return dispatched_count

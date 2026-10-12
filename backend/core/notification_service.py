from abc import ABC, abstractmethod
from typing import Optional
from core.models import Notification, User
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings


TEMPLATE_REGISTRY = {
    "welcome_onboarding": {
        "name": "Welcome Onboarding Email",
        "category": "core",
        "description": "Sent to new platform users when their account is created.",
        "mandatory": ["user_name", "login_url"],
        "optional": ["temporary_password"],
        "default_subject": "Welcome to CISO Assistant Platform",
        "default_body": "Hello ${user_name},\n\nWelcome to CISO Assistant. Your account has been activated. Please log in using the link below:\n\n${login_url}",
    },
    "password_reset": {
        "name": "Password Reset Email",
        "category": "core",
        "description": "Sent when a user requests a password reset.",
        "mandatory": ["user_name", "reset_url"],
        "optional": [],
        "default_subject": "Password Reset Request",
        "default_body": "Hello ${user_name},\n\nA password reset was requested for your account. Click the link below to set a new password:\n\n${reset_url}",
    },
    "control_assignment": {
        "name": "Control Assignment Digest Email",
        "category": "notification",
        "description": "Consolidated batch notification sent to SPOC with assigned controls.",
        "mandatory": ["spoc_name", "controls_list", "due_date", "action_url"],
        "optional": ["total_controls"],
        "default_subject": "Control Assignment Summary Notification",
        "default_body": "Hello ${spoc_name},\n\nYou have been assigned the following compliance controls:\n\n${controls_list}\n\nDue Date: ${due_date}\n\nPlease submit evidence by their respective due dates at:\n${action_url}",
    },
    "escalation_l1": {
        "name": "L1 Escalation Reminder Email",
        "category": "notification",
        "description": "Reminder sent to SPOC when evidence due date approaches/passes.",
        "mandatory": ["spoc_name", "controls_list", "due_date", "action_url"],
        "optional": [],
        "default_subject": "L1 Reminder: Pending Control Evidence Required",
        "default_body": "Hello ${spoc_name},\n\nThis is an L1 reminder for the following controls requiring evidence submission:\n\n${controls_list}\n\nOriginal Due Date: ${due_date}\nAction Required: ${action_url}",
    },
    "escalation_l2": {
        "name": "L2 Grace Period Escalation Email",
        "category": "notification",
        "description": "Grace period extension alert sent to SPOC and SPOC's Supervisor.",
        "mandatory": ["spoc_name", "supervisor_name", "controls_list", "l2_deadline", "action_url"],
        "optional": [],
        "default_subject": "L2 Grace Period Extension: Overdue Evidence Alert",
        "default_body": "Hello ${spoc_name} (Supervisor: ${supervisor_name}),\n\nAn L2 grace period deadline extension has been set for overdue controls:\n\n${controls_list}\n\nNew Extended Deadline: ${l2_deadline}\nAction Required: ${action_url}",
    },
    "escalation_l3": {
        "name": "L3 Final Grace Period Escalation Email",
        "category": "notification",
        "description": "Final grace period alert sent to SPOC, Supervisor, and Supervisor's Supervisor/Webadmin.",
        "mandatory": ["spoc_name", "supervisor_name", "controls_list", "l3_deadline", "action_url"],
        "optional": [],
        "default_subject": "L3 FINAL Escalation Notice: Immediate Action Required",
        "default_body": "URGENT - L3 Final Deadline Notice\n\nSPOC: ${spoc_name}\nSupervisor: ${supervisor_name}\n\nFinal Deadline: ${l3_deadline}\n\nPending Controls:\n${controls_list}\n\nLink: ${action_url}",
    },
    "intermediary_submission": {
        "name": "Intermediary Partner Report Upload Email",
        "category": "notification",
        "description": "Sent when a partner uploads an intermediary compliance report.",
        "mandatory": ["partner_name", "report_title", "action_url"],
        "optional": [],
        "default_subject": "New Intermediary Report Uploaded",
        "default_body": "Partner ${partner_name} uploaded report '${report_title}'.\n\nView details: ${action_url}",
    },
    "intermediary_rejection": {
        "name": "Intermediary Partner Report Rejection Email",
        "category": "notification",
        "description": "Sent when an admin rejects an intermediary partner compliance report.",
        "mandatory": ["partner_name", "report_title", "reviewer_feedback", "action_url"],
        "optional": [],
        "default_subject": "Intermediary Compliance Report Revision Requested",
        "default_body": "Hello ${partner_name},\n\nYour report '${report_title}' was reviewed and requires revision.\n\nFeedback:\n${reviewer_feedback}\n\nPlease resubmit at:\n${action_url}",
    },
    "intermediary_assignment": {
        "name": "Intermediary Business Function SPOC Assignment Email",
        "category": "notification",
        "description": "Sent when a user is assigned as SPOC for an Intermediary domain.",
        "mandatory": ["domain_name", "action_url"],
        "optional": [],
        "default_subject": "Assigned as SPOC for Intermediary Business Function",
        "default_body": "You have been assigned as SPOC for Business Function: ${domain_name}.\n\nAccess repository: ${action_url}",
    },
}


def validate_template_placeholders(template_key: str, body: str) -> tuple:
    meta = TEMPLATE_REGISTRY.get(template_key)
    if not meta:
        return True, ""
    missing = []
    for var in meta.get("mandatory", []):
        p1 = f"${{{var}}}"
        p2 = f"{{{var}}}"
        if p1 not in body and p2 not in body:
            missing.append(var)
    if missing:
        return False, f"Missing mandatory placeholders: {', '.join(['{' + m + '}' for m in missing])}"
    return True, ""


def render_custom_or_default_template(template_key: str, variables: dict, language: str = "en") -> tuple:
    from core.models import CustomEmailTemplate
    meta = TEMPLATE_REGISTRY.get(template_key, {})
    custom_tmpl = CustomEmailTemplate.objects.filter(template_key=template_key, language=language, is_active=True).first()
    if custom_tmpl:
        subject = custom_tmpl.subject
        body = custom_tmpl.body
        is_valid, _ = validate_template_placeholders(template_key, body)
        if not is_valid:
            subject = meta.get("default_subject", "")
            body = meta.get("default_body", "")
    else:
        subject = meta.get("default_subject", "")
        body = meta.get("default_body", "")

    for k, v in variables.items():
        str_val = str(v) if v is not None else ""
        subject = subject.replace(f"${{{k}}}", str_val).replace(f"{{{k}}}", str_val)
        body = body.replace(f"${{{k}}}", str_val).replace(f"{{{k}}}", str_val)

    return subject, body


class NotificationChannel(ABC):
    """Abstract base class for notification delivery channels."""

    @abstractmethod
    def deliver(self, notification: Notification) -> bool:
        pass


class InAppChannel(NotificationChannel):
    """Saves notification in database for bell icon & dropdown display."""

    def deliver(self, notification: Notification) -> bool:
        notification.save()
        return True


def _get_logo_base64(theme="light"):
    try:
        import base64, os
        from django.conf import settings
        logo_filename = "Max_Life_Insurance_logo_light.svg" if theme == "light" else "Max_Life_Insurance_logo.svg"
        candidates = [
            os.path.join(settings.BASE_DIR, "logo", logo_filename),
            os.path.join(settings.BASE_DIR, "..", "logo", logo_filename),
            os.path.join(settings.BASE_DIR, "logo", "Max_Life_Insurance_logo.svg"),
        ]
        for logo_path in candidates:
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass
    return ""


def render_official_html_email(title: str, message: str, action_url: str) -> str:
    """
    Renders an official, branded HTML email template with Max Life Insurance logo for notifications.
    """
    logo_b64 = _get_logo_base64(theme="light")
    logo_html = (
        f'<img src="data:image/svg+xml;base64,{logo_b64}" alt="Max Life Insurance Logo" style="max-height: 60px; max-width: 260px; width: auto; height: auto; display: block; margin: 0 auto;" />'
        if logo_b64
        else '<span style="font-size: 22px; font-weight: 800; color: #ffffff;">Max Life Insurance</span>'
    )
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0f172a; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0f172a; padding: 30px 10px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #1e293b; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155;">
                    <!-- OFFICIAL PLATFORM HEADER -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 24px; text-align: center; border-bottom: 2px solid #3b82f6;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center">
                                        <div style="display: inline-block; background: #ffffff; padding: 12px 24px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                                            {logo_html}
                                        </div>
                                        <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 1.8px; margin-top: 12px; font-weight: 700;">
                                            Governance, Risk & Compliance Management Platform
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <!-- EMAIL CONTENT CARD -->
                    <tr>
                        <td style="padding: 32px 28px; color: #f8fafc;">
                            <div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 16px; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; letter-spacing: 0.3px;">
                                {title}
                            </div>
                            <div style="font-size: 14px; line-height: 1.6; color: #cbd5e1; margin-bottom: 26px; background-color: #0f172a; padding: 18px; border-left: 4px solid #6366f1; border-radius: 6px;">
                                {message}
                            </div>
                            <!-- CALL TO ACTION -->
                            <div style="text-align: center; margin: 32px 0 12px 0;">
                                <a href="{action_url}" target="_blank" style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 700; padding: 14px 28px; border-radius: 8px; display: inline-block; box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4); text-transform: uppercase; letter-spacing: 0.6px;">
                                    Open CISO Assistant Platform &rarr;
                                </a>
                            </div>
                        </td>
                    </tr>
                    <!-- OFFICIAL FOOTER -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 20px 28px; text-align: center; border-top: 1px solid #334155;">
                            <p style="margin: 0 0 6px 0; font-size: 12px; color: #94a3b8; font-weight: 500;">
                                Official Security & Compliance Notification from <strong>CISO Assistant Platform</strong>.
                            </p>
                            <p style="margin: 0; font-size: 11px; color: #64748b;">
                                Confidential - Intended solely for authorized organisation users. Do not reply to this email.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


class EmailChannel(NotificationChannel):
    """Queues email for notification if send_email=True using official HTML template."""

    def deliver(self, notification: Notification) -> bool:
        if notification.send_email and not notification.email_sent:
            try:
                import re
                from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@ciso.assistant")
                base_url = getattr(settings, "CISO_ASSISTANT_URL", "http://localhost:8443")
                action_url = f"{base_url}{notification.link_url}" if notification.link_url else base_url

                # Clean title for Email Subject line (must be strictly single line with no \n, \r, or control characters)
                raw_title = notification.title or "Notification"
                clean_title = " ".join(raw_title.splitlines()).strip()
                clean_title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_title)
                
                # Truncate subject if extremely long to fit header standards, and use maxlinelen=999
                if len(clean_title) > 60:
                    clean_title = clean_title[:57] + "..."
                subject_text = f"[CISO Assistant] {clean_title}"

                # Extract pure plain text (strip HTML tags) for non-HTML email clients
                raw_msg = notification.message or ""
                plain_text_part = raw_msg.split("<ul")[0].split("<li")[0] if ("<ul" in raw_msg or "<li" in raw_msg) else raw_msg
                plain_msg_text = re.sub(r'<[^>]+>', '', plain_text_part).strip()
                plain_body = f"{clean_title}\n\n{plain_msg_text}\n\nLink: {action_url}"

                # Format HTML email body
                html_body = render_official_html_email(
                    title=clean_title,
                    message=raw_msg,
                    action_url=action_url,
                )

                from django.core.mail import EmailMultiAlternatives
                msg = EmailMultiAlternatives(
                    subject=subject_text,
                    body=plain_body,
                    from_email=from_email,
                    to=[notification.user.email],
                )
                msg.attach_alternative(html_body, "text/html")
                sent_count = msg.send(fail_silently=False)
                if sent_count > 0:
                    notification.email_sent = True
                    notification.save(update_fields=["email_sent"])
                    return True
                else:
                    return False
            except Exception as e:
                print(f"[EmailChannel] Failed to send email to {notification.user.email}: {e}")
                return False
        return False


class NotificationService:
    channels = [InAppChannel(), EmailChannel()]

    @classmethod
    def notify(
        cls,
        user: User,
        title: str,
        message: str,
        notification_type: str = "GENERAL",
        link_url: str = "",
        send_email: bool = False,
        related_object_type: str = "",
        related_object_id: str = "",
        severity: str = "info",
        event_id: str = "",
    ) -> Optional[Notification]:
        if not user:
            return None

        # True Event ID / Unique Event Hash Idempotency Check:
        # Prefers event_id when supplied to allow legitimate future reassignments while preventing duplicate retries.
        effective_object_id = event_id if event_id else related_object_id
        if related_object_type and effective_object_id:
            existing = Notification.objects.filter(
                user=user,
                notification_type=notification_type,
                related_object_type=related_object_type,
                related_object_id=effective_object_id,
                is_read=False,
                is_archived=False,
            ).first()
            if existing:
                if send_email and not existing.send_email:
                    existing.send_email = True
                    EmailChannel().deliver(existing)
                return existing

        notification = Notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link_url=link_url,
            send_email=send_email,
            related_object_type=related_object_type,
            related_object_id=effective_object_id,
            severity=severity,
        )

        for channel in cls.channels:
            channel.deliver(notification)

        return notification

    @classmethod
    def clear_notifications_for_task(cls, user: User, ref_id: str = "", notification_types: list = None, related_object_type: str = "", related_object_id: str = ""):
        """
        Auto-clears/marks as read pending notifications for a user when they respond to a task.
        """
        if not user:
            return
        qs = Notification.objects.filter(user=user, is_read=False)
        if related_object_type and related_object_id:
            qs = qs.filter(related_object_type=related_object_type, related_object_id=related_object_id)
        elif ref_id:
            qs = qs.filter(message__icontains=ref_id)
        else:
            return

        if notification_types:
            qs = qs.filter(notification_type__in=notification_types)
        qs.update(is_read=True, read_at=timezone.now())

    @classmethod
    def notify_control_assignment(cls, control_assignment):
        """
        In-platform notification for routine assignments (send_email=False to prevent email spam).
        """
        ref_id = control_assignment.requirement_node.ref_id if control_assignment.requirement_node else ""
        name = control_assignment.requirement_node.name if control_assignment.requirement_node else ""
        ca_id = str(control_assignment.id)

        if control_assignment.spoc_user:
            spoc = control_assignment.spoc_user
            cls.notify(
                user=spoc,
                title=f"New Control Assignment (SPOC): {ref_id}",
                message=f"You have been assigned as SPOC for control '{ref_id} - {name}'.",
                notification_type="ASSIGNMENT",
                link_url="/control-assignments/submit",
                send_email=False,
                related_object_type="ControlAssignment",
                related_object_id=ca_id,
            )

            # Atomic 24h Email Cooldown Check & Dispatch
            with transaction.atomic():
                locked_spoc = User.objects.select_for_update().filter(id=spoc.id).first()
                if locked_spoc:
                    now = timezone.now()
                    last_sent = locked_spoc.last_assignment_email_sent_at
                    cooldown_expired = (last_sent is None) or (last_sent <= (now - timedelta(hours=24)))

                    if cooldown_expired:
                        from core.models import ControlAssignment
                        # Fetch all pending assignments for this SPOC atomically
                        pending_assignments = list(
                            ControlAssignment.objects.filter(
                                spoc_user=locked_spoc,
                                pending_email_notification=True
                            ).select_related("requirement_node", "framework")
                        )

                        if pending_assignments:
                            # Build consolidated assignment summary
                            ctrl_html_items = []
                            ctrl_plain_items = []
                            for pa in pending_assignments:
                                p_ref = pa.requirement_node.ref_id if pa.requirement_node else "Control"
                                p_name = pa.requirement_node.name if pa.requirement_node else ""
                                p_fw = pa.framework.name if pa.framework else ""
                                ctrl_html_items.append(f"<li style='margin-bottom: 6px;'><strong>{p_ref}</strong> - {p_name} <span style='color: #94a3b8;'>({p_fw})</span></li>")
                                ctrl_plain_items.append(f"• {p_ref} - {p_name} ({p_fw})")

                            html_list = f"<ul style='margin-top: 10px; margin-bottom: 16px; padding-left: 20px;'>{''.join(ctrl_html_items)}</ul>"
                            plain_list = "\n".join(ctrl_plain_items)

                            msg_text = f"You have been assigned as SPOC for {len(pending_assignments)} control(s):\n\n{plain_list}\n\n{html_list}"

                            notif = Notification.objects.create(
                                user=locked_spoc,
                                title=f"Control Assignment Notification ({len(pending_assignments)} controls)",
                                message=msg_text,
                                notification_type=Notification.NotificationType.ASSIGNMENT,
                                link_url="/control-assignments/submit",
                                send_email=True,
                                related_object_type="ControlAssignment",
                                related_object_id=ca_id,
                            )
                            EmailChannel().deliver(notif)

                            # Atomically update notification timestamp & clear pending flags
                            locked_spoc.last_assignment_email_sent_at = now
                            locked_spoc.save(update_fields=["last_assignment_email_sent_at"])

                            sent_ids = [pa.id for pa in pending_assignments]
                            ControlAssignment.all_objects.filter(id__in=sent_ids).update(pending_email_notification=False)

        if control_assignment.reviewer_user:
            cls.notify(
                user=control_assignment.reviewer_user,
                title=f"New Control Assignment (Reviewer): {ref_id}",
                message=f"You have been assigned as Reviewer for control '{ref_id} - {name}'.",
                notification_type="ASSIGNMENT",
                link_url="/control-assignments/review",
                send_email=False,
                related_object_type="ControlAssignment",
                related_object_id=ca_id,
            )

    @classmethod
    def notify_evidence_submission(cls, target):
        """
        Notify reviewer when SPOC submits evidence. Accepts ControlAssignment or ControlEvidenceMapping.
        """
        assignment = getattr(target, "control_assignment", target)
        req_node = getattr(assignment, "requirement_node", None)
        ref_id = req_node.ref_id if req_node else ""
        name = req_node.name if req_node else ""
        ca_id = str(assignment.id) if assignment else ""

        if getattr(assignment, "spoc_user", None):
            cls.clear_notifications_for_task(assignment.spoc_user, ref_id, ["ASSIGNMENT", "ESCALATION"], related_object_type="ControlAssignment", related_object_id=ca_id)

        if getattr(assignment, "reviewer_user", None):
            cls.notify(
                user=assignment.reviewer_user,
                title=f"Evidence Submitted for Review: {ref_id}",
                message=f"SPOC has submitted evidence for control '{ref_id} - {name}'. Please review and approve/reject.",
                notification_type="EVIDENCE_SUBMITTED",
                link_url="/control-assignments/review",
                send_email=False,
                related_object_type="ControlAssignment",
                related_object_id=ca_id,
            )

    @classmethod
    def notify_reviewer_decision(cls, target, status: str = "APPROVED", feedback: str = "", approved: bool = None):
        """
        Notify SPOC of reviewer decision (Approved or Rejected).
        Rejections trigger an email notification with reviewer feedback.
        """
        if approved is not None:
            status = "APPROVED" if approved else "REJECTED"

        mapping = getattr(target, "control_evidence_mapping", None)
        assignment = getattr(mapping, "control_assignment", None) if mapping else getattr(target, "control_assignment", target)
        req_node = getattr(assignment, "requirement_node", None) if assignment else None
        ref_id = req_node.ref_id if req_node else ""
        name = req_node.name if req_node else ""
        ca_id = str(assignment.id) if assignment else ""

        if getattr(assignment, "reviewer_user", None):
            cls.clear_notifications_for_task(assignment.reviewer_user, ref_id, ["EVIDENCE_SUBMITTED"], related_object_type="ControlAssignment", related_object_id=ca_id)

        spoc = getattr(assignment, "spoc_user", None)
        if spoc:
            is_approved = (status == "APPROVED")
            n_type = "EVIDENCE_APPROVED" if is_approved else "EVIDENCE_REJECTED"
            msg = f"Your evidence for control '{ref_id} - {name}' was APPROVED." if is_approved else f"Your evidence for control '{ref_id} - {name}' was REJECTED. Reviewer Feedback: {feedback}"
            cls.notify(
                user=spoc,
                title=f"Evidence {status}: {ref_id}",
                message=msg,
                notification_type=n_type,
                link_url="/control-assignments/submit",
                send_email=not is_approved,
                related_object_type="ControlAssignment",
                related_object_id=ca_id,
            )

    @classmethod
    def notify_audit_phase_change(cls, assessment, current_phase: str, new_phase: str):
        """
        Notify assessment authors / owners when the audit phase transitions.
        """
        if not assessment:
            return
        title = f"Audit Phase Changed: {assessment.name if hasattr(assessment, 'name') else 'Assessment'}"
        message = f"Audit phase transitioned from '{current_phase}' to '{new_phase}'."
        if hasattr(assessment, "author") and assessment.author:
            cls.notify(
                user=assessment.author,
                title=title,
                message=message,
                notification_type="AUDIT_PHASE_CHANGE",
                link_url=f"/compliance-assessments/{assessment.id}",
                send_email=False,
            )

    @classmethod
    def notify_task_assignment(cls, task_node, actor_user):
        """Notify assigned user when a TaskNode is assigned."""
        if not actor_user:
            return
        node_id = str(task_node.id)
        name = task_node.task_template.name if (hasattr(task_node, 'task_template') and task_node.task_template) else "Task"
        due_str = task_node.due_date.strftime("%Y-%m-%d") if getattr(task_node, 'due_date', None) else "Not set"
        cls.notify(
            user=actor_user,
            title=f"Task Assigned: {name}",
            message=f"You have been assigned task '{name}' (Due: {due_str}).",
            notification_type="ASSIGNMENT",
            link_url=f"/task-nodes/{node_id}",
            send_email=True,
            related_object_type="TaskNode",
            related_object_id=node_id,
        )

    @classmethod
    def notify_assessment_assignment(cls, assessment, author_user):
        """Notify author/auditor when assigned to a ComplianceAssessment."""
        if not author_user:
            return
        ass_id = str(assessment.id)
        name = assessment.name if hasattr(assessment, 'name') else "Assessment"
        cls.notify(
            user=author_user,
            title=f"Audit/Assessment Assigned: {name}",
            message=f"You have been assigned as Author/Auditor for assessment '{name}'.",
            notification_type="ASSIGNMENT",
            link_url=f"/compliance-assessments/{ass_id}",
            send_email=True,
            related_object_type="ComplianceAssessment",
            related_object_id=ass_id,
        )

    @classmethod
    def notify_security_exception_assignment(cls, exception, approver_user):
        """Notify approver when assigned to a SecurityException."""
        if not approver_user:
            return
        exc_id = str(exception.id)
        name = exception.name if hasattr(exception, 'name') else "Security Exception"
        cls.notify(
            user=approver_user,
            title=f"Security Exception Review Required: {name}",
            message=f"Security exception '{name}' requires your review and approval.",
            notification_type="ASSIGNMENT",
            link_url=f"/security-exceptions/{exc_id}",
            send_email=True,
            related_object_type="SecurityException",
            related_object_id=exc_id,
        )

    @classmethod
    def notify_validation_flow_assignment(cls, validation, approver_user):
        """Notify approver when assigned to a ValidationFlow."""
        if not approver_user:
            return
        val_id = str(validation.id)
        ref_id = validation.ref_id if hasattr(validation, 'ref_id') else "Validation"
        cls.notify(
            user=approver_user,
            title=f"Validation Flow Pending Review: {ref_id}",
            message=f"Validation flow '{ref_id}' is pending your approval.",
            notification_type="ASSIGNMENT",
            link_url=f"/validation-flows/{val_id}",
            send_email=True,
            related_object_type="ValidationFlow",
            related_object_id=val_id,
        )

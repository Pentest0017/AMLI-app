import datetime
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import EscalationRule, EscalationLog, ComplianceAssessment, AssessmentControlSnapshot, ControlAssignment, User
from core.permissions import IsGlobalAdmin
from core.notification_service import NotificationService
from core.escalation_engine import log_escalation_audit_entry


class EscalationRuleSerializer(serializers.ModelSerializer):
    target_admin_email = serializers.SerializerMethodField()

    class Meta:
        model = EscalationRule
        fields = [
            "id", "name", "description", "is_active", "trigger_baseline",
            "escalation_steps", "target_admin_email", "created_at"
        ]

    def get_target_admin_email(self, obj):
        steps = obj.escalation_steps or {}
        user_id = steps.get("target_admin_user_id")
        if user_id:
            u = User.objects.filter(id=user_id).first()
            return u.email if u else ""
        return ""


class EscalationRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = EscalationRuleSerializer
    queryset = EscalationRule.objects.all().order_by("created_at")

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "is_superuser", False) and getattr(user, "platform_role", "") not in ["superadmin", "webadmin", "admin"]:
            return EscalationRule.objects.none()
        
        # Seed initial rules for any missing level (L1, L2, L3)
        existing_levels = set()
        for r in EscalationRule.objects.all():
            steps = r.escalation_steps or {}
            lvl = steps.get("level", 1)
            existing_levels.add(lvl)

        if 1 not in existing_levels:
            EscalationRule.objects.create(
                name="L1: SPOC Reminder",
                description="Level 1 Escalation for SPOC",
                is_active=True,
                escalation_steps={
                    "level": 1,
                    "interval_value": 15,
                    "interval_unit": "minutes",
                    "recipient_role": "SPOC",
                    "target_admin_user_id": None
                }
            )
        if 2 not in existing_levels:
            EscalationRule.objects.create(
                name="L2: SPOC + Reviewer",
                description="Level 2 Escalation for SPOC and Reviewer",
                is_active=True,
                escalation_steps={
                    "level": 2,
                    "interval_value": 1,
                    "interval_unit": "hours",
                    "recipient_role": "REVIEWER",
                    "target_admin_user_id": None
                }
            )
        if 3 not in existing_levels:
            EscalationRule.objects.create(
                name="L3: SPOC + Reviewer + Webadmin",
                description="Level 3 Escalation for SPOC, Reviewer and Webadmin",
                is_active=True,
                escalation_steps={
                    "level": 3,
                    "interval_value": 1,
                    "interval_unit": "days",
                    "recipient_role": "WEBADMIN",
                    "target_admin_user_id": None
                }
            )

        return super().get_queryset()

    def update_rule_instance(self, instance, data):
        name = data.get("name", instance.name)
        raw_active = data.get("is_active", instance.is_active)
        if isinstance(raw_active, str):
            is_active = raw_active.lower() in ["true", "1", "t", "yes"]
        else:
            is_active = bool(raw_active)
        
        steps = instance.escalation_steps or {}
        if "level" in data:
            steps["level"] = int(data["level"])
        if "interval_value" in data:
            steps["interval_value"] = int(data["interval_value"])
        if "interval_unit" in data:
            steps["interval_unit"] = str(data["interval_unit"])
        if "recipient_role" in data:
            steps["recipient_role"] = str(data["recipient_role"])
        if "target_admin_user_id" in data:
            steps["target_admin_user_id"] = data["target_admin_user_id"]

        instance.name = name
        instance.is_active = is_active
        if "trigger_baseline" in data:
            instance.trigger_baseline = data["trigger_baseline"]
        instance.escalation_steps = steps
        instance.save()
        return instance

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        updated_instance = self.update_rule_instance(instance, request.data)
        serializer = self.get_serializer(updated_instance)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class EscalationAdminUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Dynamically returns active Webadmin and Admin user accounts from DB.
        Excludes superadmin accounts.
        """
        users = User.objects.filter(
            is_active=True,
            platform_role__in=["webadmin", "admin"]
        ).exclude(
            is_superuser=True
        ).exclude(
            platform_role="superadmin"
        ).order_by("email")

        results = []
        for u in users:
            name = f"{u.first_name} {u.last_name}".strip()
            results.append({
                "id": str(u.id),
                "email": u.email,
                "name": name if name else u.email,
                "role": u.platform_role,
            })
        return Response(results)


class EscalationManualTriggerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Level-based manual bulk escalation endpoint.
        Uses configured rules for target recipients and admin accounts dynamically.
        """
        user = request.user
        if getattr(user, "platform_role", "") not in ["superadmin", "webadmin", "admin"]:
            return Response({"error": "Only Admins, Webadmins or Superadmins can trigger escalations."}, status=status.HTTP_403_FORBIDDEN)

        level = int(request.data.get("level", 1))
        assignment_ids = request.data.get("assignment_ids", [])
        
        assignments_qs = ControlAssignment.objects.filter(is_active=True, spoc_user__isnull=False)
        if assignment_ids:
            assignments_qs = assignments_qs.filter(id__in=assignment_ids)

        if not assignments_qs.exists():
            return Response({"error": "No valid control assignments found for escalation."}, status=status.HTTP_400_BAD_REQUEST)

        rules = EscalationRule.objects.all()
        target_rule = None
        for r in rules:
            r_level = r.escalation_steps.get("level") if isinstance(r.escalation_steps, dict) else None
            if r_level == level:
                target_rule = r
                break

        target_admin_user_id = target_rule.escalation_steps.get("target_admin_user_id") if (target_rule and isinstance(target_rule.escalation_steps, dict)) else None
        
        webadmins = []
        if target_admin_user_id:
            specific_admin = User.objects.filter(id=target_admin_user_id, is_active=True).exclude(is_superuser=True).exclude(platform_role="superadmin").first()
            if specific_admin:
                webadmins = [specific_admin]
        
        if not webadmins:
            webadmins = list(
                User.objects.filter(is_active=True, platform_role__in=["webadmin", "admin"])
                .exclude(is_superuser=True)
                .exclude(platform_role="superadmin")
            )

        today = datetime.date.today()
        emails_sent = 0
        already_sent_today_count = 0
        newly_sent_count = 0

        # Group assignments by target recipient for this escalation level
        # Level 1: SPOC Only
        # Level 2: SPOC & Reviewer
        # Level 3: SPOC, Reviewer & Target Webadmin
        recipient_map = {}  # recipient_user -> list of (assignment, role_title)

        from core.escalation_engine import is_assignment_cleared

        for assignment in assignments_qs:
            if is_assignment_cleared(assignment):
                continue
            recipients = []
            recipient_ids = set()

            if level == 1:
                if assignment.spoc_user:
                    recipients.append((assignment.spoc_user, "SPOC"))
            elif level == 2:
                if assignment.spoc_user:
                    recipients.append((assignment.spoc_user, "SPOC"))
                    recipient_ids.add(assignment.spoc_user.id)
                if assignment.reviewer_user and assignment.reviewer_user.id not in recipient_ids:
                    recipients.append((assignment.reviewer_user, "Reviewer"))
                    recipient_ids.add(assignment.reviewer_user.id)
            elif level >= 3:
                if assignment.spoc_user:
                    recipients.append((assignment.spoc_user, "SPOC"))
                    recipient_ids.add(assignment.spoc_user.id)
                if assignment.reviewer_user and assignment.reviewer_user.id not in recipient_ids:
                    recipients.append((assignment.reviewer_user, "Reviewer"))
                    recipient_ids.add(assignment.reviewer_user.id)
                for wa in webadmins:
                    if wa.id not in recipient_ids:
                        recipients.append((wa, f"Webadmin ({wa.email})"))
                        recipient_ids.add(wa.id)

            for recipient_user, role_title in recipients:
                if recipient_user not in recipient_map:
                    recipient_map[recipient_user] = []
                recipient_map[recipient_user].append((assignment, role_title))

        for recipient_user, item_list in recipient_map.items():
            ctrl_html_items = []
            ctrl_plain_items = []
            distinct_assignments = []

            for assignment, role_title in item_list:
                audit = ComplianceAssessment.objects.filter(framework=assignment.framework).first()
                ref_id = assignment.requirement_node.ref_id if assignment.requirement_node else "Control"
                name = assignment.requirement_node.name if assignment.requirement_node else ""
                fw_name = assignment.framework.name if assignment.framework else ""
                step_label = f"MANUAL_L{level}_{role_title}"

                was_sent_today = EscalationLog.objects.filter(
                    control_assignment=assignment,
                    step_label__icontains=f"L{level}",
                    recipient_user=recipient_user,
                    escalation_date=today,
                    trigger_type="MANUAL",
                ).exists()

                if was_sent_today:
                    already_sent_today_count += 1
                else:
                    newly_sent_count += 1

                ctrl_html_items.append(f"<li style='margin-bottom: 6px;'><strong>{ref_id}</strong> - {name} <span style='color: #94a3b8;'>({fw_name})</span></li>")
                ctrl_plain_items.append(f"• {ref_id} - {name} ({fw_name})")
                distinct_assignments.append((assignment, audit, step_label))

            html_list = f"<ul style='margin-top: 10px; margin-bottom: 16px; padding-left: 20px;'>{''.join(ctrl_html_items)}</ul>"
            plain_list = "\n".join(ctrl_plain_items)

            count_str = f"{len(item_list)} control(s)" if len(item_list) > 1 else "1 control"
            title_text = f"Manual Escalation (L{level}): {count_str}"
            msg_text = f"Level {level} Escalation issued by {user.email} for {count_str}:\n\n{plain_list}\n\n{html_list}"

            notif = NotificationService.notify(
                user=recipient_user,
                title=title_text,
                message=msg_text,
                notification_type="ESCALATION",
                link_url="/control-assignments/submit",
                send_email=True,
            )

            email_success = notif.email_sent if (notif and hasattr(notif, 'email_sent')) else False
            if email_success:
                emails_sent += 1

            for assignment, audit, step_label in distinct_assignments:
                EscalationLog.objects.create(
                    compliance_assessment=audit,
                    control_assignment=assignment,
                    trigger_type="MANUAL",
                    triggered_by=user,
                    recipient_user=recipient_user,
                    recipient_email=recipient_user.email,
                    step_label=step_label,
                    escalation_date=today,
                    email_sent=True,
                )
                log_escalation_audit_entry(assignment, recipient_user, step_label, "MANUAL", actor=user)

        if already_sent_today_count > 0 and newly_sent_count == 0:
            msg = f"Level {level} Escalation re-dispatched! (Note: Escalation mail was already sent earlier today to recipient)."
        elif already_sent_today_count > 0:
            msg = f"Level {level} Escalation sent successfully! ({newly_sent_count} new email(s) sent, {already_sent_today_count} re-sent as mail was already sent earlier today)."
        else:
            msg = f"Level {level} Escalation sent successfully! ({emails_sent} email(s) dispatched)."

        return Response({
            "status": "success",
            "message": msg,
            "processed_count": assignments_qs.count(),
            "emails_sent": emails_sent,
            "already_sent_today": already_sent_today_count > 0,
        })


class EscalationLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not getattr(user, "is_superuser", False) and getattr(user, "platform_role", "") not in ["superadmin", "webadmin", "admin"]:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        assessment_id = request.query_params.get("assessment_id")
        logs_qs = EscalationLog.objects.all().select_related(
            "compliance_assessment", "control_assignment", "control_assignment__requirement_node", "triggered_by", "recipient_user"
        ).order_by("-created_at")

        if assessment_id:
            logs_qs = logs_qs.filter(compliance_assessment_id=assessment_id)

        results = []
        for log in logs_qs[:100]:
            ref_id = log.control_assignment.requirement_node.ref_id if (log.control_assignment and log.control_assignment.requirement_node) else ""
            ctrl_name = log.control_assignment.requirement_node.name if (log.control_assignment and log.control_assignment.requirement_node) else ""

            results.append({
                "id": str(log.id),
                "assessment_name": log.compliance_assessment.name if log.compliance_assessment else "Control Assignment Escalation",
                "control_ref_id": ref_id,
                "control_name": ctrl_name,
                "trigger_type": log.trigger_type,
                "step_label": log.step_label,
                "recipient_email": log.recipient_email,
                "email_sent": log.email_sent,
                "escalation_date": log.escalation_date.isoformat() if log.escalation_date else "",
                "created_at": timezone.localtime(log.created_at).strftime("%d/%m/%Y, %I:%M:%S %p") if log.created_at else "",
                "triggered_by": log.triggered_by.email if log.triggered_by else "System",
            })

        return Response({
            "count": len(results),
            "results": results,
        })


class EscalationScheduleView(APIView):
    permission_classes = [IsAuthenticated, IsGlobalAdmin]

    def post(self, request):
        level = str(request.data.get("level", "L1")).upper()
        target_date_str = request.data.get("target_date")
        assignment_ids = request.data.get("assignment_ids", [])

        if not target_date_str or not assignment_ids:
            return Response({"error": "target_date and assignment_ids are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        from core.escalation_engine import schedule_escalation_level
        assignments = ControlAssignment.objects.filter(id__in=assignment_ids, is_active=True)

        count = 0
        for ca in assignments:
            schedule_escalation_level(ca, level, target_date, actor=request.user)
            count += 1

        return Response({
            "status": "success",
            "message": f"Successfully scheduled {level} escalation for {count} control assignment(s) on {target_date_str}.",
            "scheduled_count": count,
        })

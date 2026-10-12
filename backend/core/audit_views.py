import json
from rest_framework import viewsets, serializers, permissions
from auditlog.models import LogEntry
def is_user_admin(user):
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, 'platform_role', '')
    return user.is_admin or user.is_superuser or role in ['webadmin', 'superadmin', 'admin']


class LogEntrySerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()
    content_type_name = serializers.SerializerMethodField()
    object_repr = serializers.SerializerMethodField()
    changes_summary = serializers.SerializerMethodField()

    class Meta:
        model = LogEntry
        fields = [
            'id',
            'action',
            'actor',
            'actor_email',
            'object_pk',
            'object_repr',
            'changes',
            'changes_summary',
            'timestamp',
            'content_type_name',
        ]

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor else "System"

    def get_content_type_name(self, obj):
        if not obj.content_type:
            return "Resource"
        name = obj.content_type.name.title()
        if "Intermediary" in name:
            name = name.replace("Intermediary", "").strip()
        return name

    def get_object_repr(self, obj):
        raw_repr = obj.object_repr or ""
        ct_name = (obj.content_type.name if obj.content_type else "").lower()

        # Format raw UUIDs or unformatted strings into clear human-readable titles
        if "escalation" in ct_name and "log" in ct_name:
            try:
                from core.models import EscalationLog
                log_obj = EscalationLog.objects.filter(pk=obj.object_pk).select_related("control_assignment").first()
                if log_obj:
                    ref = log_obj.control_assignment.requirement_node.ref_id if (log_obj.control_assignment and log_obj.control_assignment.requirement_node) else ""
                    return f"{log_obj.step_label} - {ref} ({log_obj.recipient_email})"
            except Exception:
                pass
            return f"Escalation Alert -> {raw_repr[:8]}"

        if "notification" in ct_name:
            try:
                from core.models import Notification
                notif = Notification.objects.filter(pk=obj.object_pk).select_related("user").first()
                if notif:
                    return f"{notif.title} ({notif.user.email})"
            except Exception:
                pass
            return f"System Notification -> {raw_repr[:8]}"

        if "control" in ct_name and "assignment" in ct_name:
            try:
                from core.models import ControlAssignment
                ca = ControlAssignment.objects.filter(pk=obj.object_pk).select_related("requirement_node", "spoc_user").first()
                if ca and ca.requirement_node:
                    return f"Control {ca.requirement_node.ref_id} - {ca.requirement_node.name}"
            except Exception:
                pass

        if "evidence" in ct_name:
            try:
                from core.models import Evidence
                ev = Evidence.objects.filter(pk=obj.object_pk).first()
                if ev:
                    return f"Evidence: {ev.name}"
            except Exception:
                pass

        # If object_repr looks like a raw UUID (contains 4 dashes and 36 chars), format nicely
        if len(raw_repr) == 36 and raw_repr.count("-") == 4:
            resource_title = self.get_content_type_name(obj)
            return f"{resource_title} #{raw_repr[:8]}"

        return raw_repr

    def get_changes_summary(self, obj):
        repr_str = self.get_object_repr(obj)
        ct_name = (obj.content_type.name if obj.content_type else "").lower()

        try:
            changes_dict = json.loads(obj.changes or "{}")
            if isinstance(changes_dict, dict) and "event" in changes_dict:
                event = changes_dict["event"]
                if event == "login":
                    return f"User Logged In - {repr_str}"
                if event == "logout":
                    return f"User Logged Out - {repr_str}"
        except Exception:
            pass

        if "feature" in ct_name or "toggle" in ct_name:
            if obj.action == LogEntry.Action.CREATE:
                return f"Access Right Created - {repr_str}"
            if obj.action == LogEntry.Action.DELETE:
                return f"Access Right Deleted - {repr_str}"
            return f"Access Right Matrix Updated - {repr_str}"

        if "user group" in ct_name or "usergroup" in ct_name:
            if obj.action == LogEntry.Action.CREATE:
                return f"User Group Created - {repr_str}"
            if obj.action == LogEntry.Action.DELETE:
                return f"User Group Deleted - {repr_str}"
            return f"User Group Updated - {repr_str}"

        if "role assignment" in ct_name or "roleassignment" in ct_name:
            if obj.action == LogEntry.Action.CREATE:
                return f"Role Assignment Granted - {repr_str}"
            if obj.action == LogEntry.Action.DELETE:
                return f"Role Assignment Revoked - {repr_str}"
            return f"Role Assignment Updated - {repr_str}"

        if "user" in ct_name:
            if obj.action == LogEntry.Action.CREATE:
                return f"User Account Created - {repr_str}"
            if obj.action == LogEntry.Action.DELETE:
                return f"User Account Deleted - {repr_str}"
            return f"User Account Updated - {repr_str}"

        if "assignment" in ct_name:
            return f"Control Assignment Updated - {repr_str}"
        if "report" in ct_name:
            if obj.action == LogEntry.Action.CREATE:
                return f"Report Uploaded - {repr_str}"
            if obj.action == LogEntry.Action.DELETE:
                return f"Report Deleted - {repr_str}"
            return f"Report Updated - {repr_str}"
        if "folder" in ct_name:
            if obj.action == LogEntry.Action.CREATE:
                return f"Folder Created - {repr_str}"
            if obj.action == LogEntry.Action.DELETE:
                return f"Folder Deleted - {repr_str}"
            return f"Folder Updated - {repr_str}"

        if obj.action == LogEntry.Action.CREATE:
            return f"Created {obj.content_type.name if obj.content_type else 'Resource'} - {repr_str}"
        if obj.action == LogEntry.Action.DELETE:
            return f"Deleted {obj.content_type.name if obj.content_type else 'Resource'} - {repr_str}"
        if obj.action == LogEntry.Action.UPDATE:
            return f"Updated {obj.content_type.name if obj.content_type else 'Resource'} - {repr_str}"

        return repr_str


from rest_framework.pagination import LimitOffsetPagination


class AuditLogPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 500


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogEntrySerializer
    pagination_class = AuditLogPagination

    def get_queryset(self):
        user = self.request.user
        if not is_user_admin(user):
            return LogEntry.objects.none()
        return LogEntry.objects.all().select_related('actor', 'content_type').order_by('-timestamp')


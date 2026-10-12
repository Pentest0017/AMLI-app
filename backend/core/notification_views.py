from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.db.models import Q
from knox.auth import TokenAuthentication
from rest_framework.authentication import get_authorization_header

from core.models import Notification


class FlexibleTokenAuthentication(TokenAuthentication):
    """
    Extends Knox TokenAuthentication to read the token from either:
    1. Already authenticated Django HttpRequest user (via Session / Middleware)
    2. Standard 'Authorization: Token <token>' HTTP header
    3. 'token' browser cookie (for client-side AJAX/fetch calls)
    """

    def authenticate(self, request):
        django_user = getattr(getattr(request, "_request", None), "user", None)
        if django_user and django_user.is_authenticated:
            return (django_user, None)

        # 1. Try standard Authorization header first
        auth_header = get_authorization_header(request).split()
        if auth_header:
            try:
                return super().authenticate(request)
            except Exception:
                pass

        # 2. Try 'token' cookie if header is absent
        raw_token = request.COOKIES.get("token")
        if not raw_token:
            return None

        try:
            user, auth_token = self.authenticate_credentials(raw_token.encode("utf-8"))
            return (user, auth_token)
        except Exception:
            return None


def _user_notification_q(user):
    q = Q(user=user)
    if user and getattr(user, "email", None):
        q |= Q(user__email=user.email)
    return q


class NotificationListView(APIView):
    authentication_classes = [FlexibleTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        unread_only = request.query_params.get("unread_only", "").lower() == "true"
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20

        qs = Notification.objects.filter(
            _user_notification_q(user),
            is_archived=False
        )

        if unread_only:
            qs = qs.filter(is_read=False)

        notifications = qs.order_by("-created_at")[:limit]
        unread_count = Notification.objects.filter(
            _user_notification_q(user),
            is_read=False,
            is_archived=False
        ).count()

        results = []
        for n in notifications:
            results.append({
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "notification_type": n.notification_type,
                "link_url": n.link_url,
                "is_read": n.is_read,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "related_object_type": getattr(n, "related_object_type", ""),
                "related_object_id": getattr(n, "related_object_id", ""),
                "severity": getattr(n, "severity", "info"),
            })

        return Response({
            "unread_count": unread_count,
            "results": results,
        })


class NotificationUnreadCountView(APIView):
    authentication_classes = [FlexibleTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        count = Notification.objects.filter(
            _user_notification_q(user),
            is_read=False,
            is_archived=False
        ).count()
        return Response({"count": count, "unread_count": count})


class NotificationMarkReadView(APIView):
    authentication_classes = [FlexibleTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        user = request.user
        # Strict user-specific ownership verification
        n = Notification.objects.filter(
            id=notification_id,
            user=user
        ).first()

        if not n and user and getattr(user, "email", None):
            # Check by email fallback if user objects differ
            n = Notification.objects.filter(id=notification_id, user__email=user.email).first()

        if not n:
            return Response(
                {"error": "Notification not found or access denied."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not n.is_read:
            n.is_read = True
            n.read_at = timezone.now()
            n.save(update_fields=["is_read", "read_at"])

        return Response({"status": "success", "id": str(n.id), "is_read": True})


class NotificationMarkAllReadView(APIView):
    authentication_classes = [FlexibleTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        updated_cnt = Notification.objects.filter(
            _user_notification_q(user),
            is_read=False,
            is_archived=False
        ).update(is_read=True, read_at=timezone.now())

        return Response({"status": "success", "updated_count": updated_cnt})


class NotificationMarkReadByTaskView(APIView):
    authentication_classes = [FlexibleTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        link_url = request.data.get("link_url", "")
        related_object_type = request.data.get("related_object_type", "")
        related_object_id = request.data.get("related_object_id", "")

        qs = Notification.objects.filter(
            _user_notification_q(user),
            is_read=False,
            is_archived=False
        )

        if related_object_type and related_object_id:
            qs = qs.filter(related_object_type=related_object_type, related_object_id=related_object_id)
        elif link_url:
            qs = qs.filter(link_url=link_url)
        else:
            return Response({"status": "error", "message": "No matching task target provided."}, status=status.HTTP_400_BAD_REQUEST)

        updated_cnt = qs.update(is_read=True, read_at=timezone.now())
        return Response({"status": "success", "updated_count": updated_cnt})

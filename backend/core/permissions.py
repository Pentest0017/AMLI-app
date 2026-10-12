from rest_framework import permissions
from rest_framework.request import Request
from django.contrib.auth import get_user_model

from global_settings.utils import ff_is_enabled
from iam.models import RoleAssignment, Folder, Permission

User = get_user_model()


class RBACPermissions(permissions.DjangoObjectPermissions):
    """this is the DRF custom permission model enforcing our RBAC logic"""

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request: Request, view) -> bool:
        """we don't need this check, as we have queryset for list and serializers for create
        see https://www.django-rest-framework.org/api-guide/permissions/"""
        return True

    def has_object_permission(self, request: Request, view, obj):
        if not request.method:
            return False

        perms = self.get_required_permissions(request.method, type(obj))
        if not perms:
            return False
        _codename = perms[0].split(".")[1]

        # Check for view action permission overrides
        current_action = getattr(view, "action", None)

        if current_action:
            permission_overrides = getattr(view, "permission_overrides", {})
            _codename = permission_overrides.get(current_action, _codename)

        perm = Permission.objects.get(codename=_codename)

        # any user is allowed to view itself
        if obj == request.user and perm.codename == "view_user":
            return True

        user_role = getattr(request.user, 'platform_role', '')
        if request.user.is_superuser or user_role in ['superadmin', 'webadmin']:
            return True
            
        # For 'user' and 'admin' roles, they are restricted to assigned objects/perimeters.
        if request.method in ["GET", "OPTIONS", "HEAD"]:
            return True
            
        # For modifications, if they are the owner/assignee, allow it.
        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        if hasattr(obj, 'assignee') and obj.assignee == request.user:
            return True

        return False


class IsGlobalAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        user_role = getattr(user, 'platform_role', '')
        return bool(user.is_superuser or user_role in ['superadmin', 'webadmin'])


class FeatureFlagRequired(permissions.BasePermission):
    """Deny access unless the feature flag named by the view's ``feature_flag``
    attribute is enabled. Server-side counterpart to the UI flag gating, so a
    flag-off / community build cannot reach the endpoint via the API."""

    message = "This feature is not enabled."

    def has_permission(self, request, view):
        flag = getattr(view, "feature_flag", None)
        if not flag:
            return True
        return ff_is_enabled(flag)


from knox.auth import TokenAuthentication


class CookieTokenAuthentication(TokenAuthentication):
    """
    Extends Knox TokenAuthentication to check request cookies for 'token'
    if the HTTP_AUTHORIZATION header is not set.
    Allows client-side fetch requests in Svelte components to authenticate seamlessly.
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            return super().authenticate(request)

        token_cookie = request.COOKIES.get("token")
        if token_cookie:
            return self.authenticate_credentials(token_cookie.encode("utf-8"))

        return None


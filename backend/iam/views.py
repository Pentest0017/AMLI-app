from base64 import urlsafe_b64decode
from datetime import timedelta

import structlog
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.contrib.auth import get_user_model, login, logout
from django.db import transaction
from django.db.models import Q, Exists, OuterRef
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import ensure_csrf_cookie
from knox import crypto
from knox.auth import TokenAuthentication, get_token_model, knox_settings
from knox.models import AuthToken
from knox.views import DateTimeField
from rest_framework import permissions, serializers, status, views
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_401_UNAUTHORIZED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from django.conf import settings

from global_settings.models import GlobalSettings
from core.models import Actor
from .models import Folder, PersonalAccessToken, RoleAssignment, SCIMToken, FeatureToggle
from core.permissions import IsGlobalAdmin, FeatureFlagRequired
from .serializers import (
    ChangePasswordSerializer,
    PersonalAccessTokenReadSerializer,
    DisableMFASerializer,
    ResetPasswordConfirmSerializer,
    SetPasswordSerializer,
    FeatureToggleSerializer,
)

logger = structlog.get_logger(__name__)

User = get_user_model()


class LogoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(ensure_csrf_cookie)
    def post(self, request) -> Response:
        try:
            current_user = request.user
            logger.info("logout request", user=current_user)
            try:
                auth_header = request.META.get("HTTP_AUTHORIZATION")
                if auth_header and " " in auth_header:
                    access_token = auth_header.split(" ")[1]
                    digest = crypto.hash_token(access_token)
                    auth_token = AuthToken.objects.get(digest=digest)
                    auth_token.delete()
                else:
                    logger.warning(
                        "No valid authorization header found during logout",
                        user=current_user,
                    )
            except Exception as e:
                logger.error(
                    "Error deleting token during logout",
                    user=current_user,
                    error=str(e),
                )
            if current_user and getattr(current_user, 'is_authenticated', False):
                try:
                    from auditlog.models import LogEntry
                    from django.contrib.contenttypes.models import ContentType
                    import json
                    LogEntry.objects.create(
                        content_type=ContentType.objects.get_for_model(current_user),
                        object_pk=str(current_user.pk),
                        object_id=current_user.pk,
                        object_repr=getattr(current_user, "email", str(current_user)),
                        action=LogEntry.Action.ACCESS,
                        actor=current_user,
                        changes=json.dumps({"event": "logout", "logout": True, "email": current_user.email})
                    )
                except Exception as log_err:
                    logger.error("Failed to record logout audit entry", error=str(log_err))

            logout(request)
            logger.info("logout successful", user=current_user)
        except Exception as e:
            logger.error("logout failed", error=str(e))
        return Response({"message": "Logged out successfully."}, status=HTTP_200_OK)


class PersonalAccessTokenViewSet(views.APIView):
    def get_queryset(self):
        return PersonalAccessToken.objects.filter(auth_token__user=self.request.user)

    def get_context(self):
        return {"request": self.request, "format": self.format_kwarg, "view": self}

    def get_token_prefix(self):
        return knox_settings.TOKEN_PREFIX

    def get_token_limit_per_user(self):
        return 5

    def get_expiry_datetime_format(self):
        return knox_settings.EXPIRY_DATETIME_FORMAT

    def format_expiry_datetime(self, expiry):
        datetime_format = self.get_expiry_datetime_format()
        return DateTimeField(format=datetime_format).to_representation(expiry)

    def create_token(self, expiry):
        token_prefix = self.get_token_prefix()
        return get_token_model().objects.create(
            user=self.request.user, expiry=expiry, prefix=token_prefix
        )

    def get_post_response_data(self, request, token, name, instance):
        data = {
            "name": name,
            "expiry": self.format_expiry_datetime(instance.expiry),
            "token": token,
        }
        return data

    def get_post_response(self, request, token, name, instance):
        data = self.get_post_response_data(request, token, name, instance)
        return Response(data)

    def post(self, request, format=None):
        if request.user.is_third_party:
            return Response(
                {"error": "Forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        token_limit_per_user = self.get_token_limit_per_user()
        name = request.data.get("name")
        try:
            expiry_days = int(request.data.get("expiry", 30))
            if expiry_days <= 0:
                raise ValueError
        except TypeError, ValueError:
            return Response(
                {"error": "Expiry must be a positive integer (days)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if token_limit_per_user is not None:
            now = timezone.now()
            token = request.user.auth_token_set.filter(expiry__gt=now).filter(
                personalaccesstoken__isnull=False
            )
            if token.count() >= token_limit_per_user:
                return Response(
                    {"error": "errorMaxPatAmountExceeded"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        instance, token = self.create_token(timedelta(days=int(expiry_days)))
        pat = PersonalAccessToken.objects.create(auth_token=instance, name=name)
        return self.get_post_response(request, token, pat.name, pat.auth_token)

    def get(self, request, *args, **kwargs):
        """
        Get all personal access tokens for the user.
        """
        queryset = self.get_queryset()
        serializer = PersonalAccessTokenReadSerializer(
            queryset, many=True, context=self.get_context()
        )
        return Response(serializer.data)


class AuthTokenDetailView(views.APIView):
    def delete(self, request, *args, **kwargs):
        if request.user.is_third_party:
            return Response(
                {"error": "Forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            token = AuthToken.objects.get(digest=kwargs["pk"])
            if token.user != request.user:
                return Response(
                    {"error": "You do not have permission to delete this token."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            token.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except AuthToken.DoesNotExist:
            logger.info(
                "Attempt to delete non-existent token",
                digest=kwargs["pk"],
                user=request.user.id,
            )
            return Response(
                {"error": "Token not found or already deleted."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                "Error deleting token",
                error=str(e),
                digest=kwargs["pk"],
                user=request.user.id,
            )
            return Response(
                {"error": "Failed to delete token due to an internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CurrentUserView(views.APIView):
    # Is this condition really necessary if we have permission_classes = [permissions.IsAuthenticated] ?
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "You are not logged in. Please ensure you are logged in."},
                status=HTTP_401_UNAUTHORIZED,
            )

        # getting only what we need
        user_groups_data = list(request.user.user_groups.values("name", "builtin"))
        user_groups = [(ug["name"], ug["builtin"]) for ug in user_groups_data]

        accessible_domains = RoleAssignment.get_accessible_folder_ids(
            Folder.get_root_folder(), request.user, Folder.ContentType.DOMAIN
        )

        domain_permissions = RoleAssignment.get_permissions_per_folder(
            principal=request.user, recursive=True
        )
        domain_permissions = {
            k: list(v) for k, v in domain_permissions.items()
        }  # this what matters

        def get_active_features(user):
            all_keys = list(FeatureToggle.objects.values_list("key", flat=True))
            if not all_keys:
                all_keys = [
                    "home", "quickStart", "users", "logs", "features", "accessRights", "riskAssessments", "complianceAssessments",
                    "vulnerabilities", "incidents", "ebiosRM", "quantitativeRiskStudies",
                    "processingsRegister", "tprmOverview", "analytics", "reports",
                    "companyHierarchy", "frameworks", "threats", "securityAdvisories",
                    "cwes", "referenceControls", "requirementMappingSets", "riskMatrices",
                    "assets", "appliedControls", "documents", "calendar", "xRays", "tasks",
                    "libraries", "policies", "organisationIssues", "organisationObjectives",
                    "riskAcceptances", "securityExceptions", "intermediaryAssignments",
                    "reportRepository", "reportGeneration", "controlAssignments", "evidenceRepository",
                    "escalationRules", "defaultersTracker", "evidences", "recap",
                    "mailTemplates", "reportTemplates", "assignmentSettings"
                ]
            if getattr(user, "is_superuser", False) or getattr(user, "platform_role", None) == "superadmin":
                return all_keys

            try:
                db_toggles = {ft.key: ft for ft in FeatureToggle.objects.all()}
            except Exception:
                db_toggles = {}

            role = getattr(user, "platform_role", None)

            if role == "webadmin":
                res = []
                for k in all_keys:
                    if k in ["features", "accessRights", "users", "logs", "settings"]:
                        res.append(k)
                        continue
                    toggle = db_toggles.get(k)
                    if toggle and not toggle.enabled_for_web_admin and user not in toggle.user_exceptions.all():
                        continue
                    res.append(k)
                final_res = set(res)
                final_res.add("accessRights")
                final_res.add("features")
                return list(final_res)

            if role == "admin":
                res = []
                for k in all_keys:
                    toggle = db_toggles.get(k)
                    if toggle and not toggle.enabled_for_admin and user not in toggle.user_exceptions.all():
                        continue
                    res.append(k)
                return list(set(res))

            # Regular user
            res = []
            for k in all_keys:
                toggle = db_toggles.get(k)
                if toggle and not toggle.enabled_for_user and user not in toggle.user_exceptions.all():
                    continue
                res.append(k)
            return list(set(res))

        res_data = {
            "id": request.user.id,
            "actor_id": request.user.actor.id,
            "all_actor_ids": [str(a.id) for a in Actor.get_all_for_user(request.user)],
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "is_active": request.user.is_active,
            "date_joined": request.user.date_joined,
            "user_groups": user_groups,
            "roles": request.user.get_roles(),
            "permissions": request.user.permissions,
            "is_third_party": request.user.is_third_party,
            "is_auditee": request.user.is_auditee,
            "is_admin": request.user.platform_role in ["admin", "webadmin", "superadmin"] or request.user.is_superuser,
            "is_local": request.user.is_local,
            "is_sso": request.user.is_sso,
            "platform_role": request.user.platform_role,
            "active_features": get_active_features(request.user),
            "accessible_domains": [str(f) for f in accessible_domains],
            "domain_permissions": domain_permissions,
            "root_folder_id": Folder.get_root_folder().id,
            "preferences": request.user.preferences,
            "has_mfa_enabled": request.user.has_mfa_enabled(),
            "is_superuser": request.user.is_superuser,
        }
        return Response(res_data, status=HTTP_200_OK)


class SessionTokenView(views.APIView):
    """
    API Endpoint for getting the session token from an access token
    This is needed for allauth's authentication flows.
    """

    def post(self, request):
        access_token = request.META.get("HTTP_AUTHORIZATION").split(" ")[1]
        if not access_token:
            return Response(
                {"error": "No access token provided"}, status=HTTP_401_UNAUTHORIZED
            )
        # Get user from token
        auth = TokenAuthentication()
        user, _ = auth.authenticate_credentials(access_token.encode())
        if not user:
            return Response(
                {"error": "Invalid access token"}, status=HTTP_401_UNAUTHORIZED
            )
        # Log the user in and get the session token
        # This token is used for allauth's authentication flows
        login(request, user)
        session_token = request.session.session_key
        return Response({"token": session_token})


class PasswordResetView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def post(self, request):
        email = request.data["email"]  # type: ignore
        associated_user = User.objects.filter(email__iexact=email).first()
        if settings.EMAIL_HOST or settings.EMAIL_HOST_RESCUE:
            if associated_user is not None and associated_user.is_local:
                try:
                    logger.info(
                        "Attempting to send password reset email", recipient=email
                    )
                    associated_user.mailing(
                        email_template_name="registration/password_reset_email.html",
                        subject=_("CISO Assistant: Password Reset"),
                    )
                    logger.info(
                        "Password reset email request processed", recipient=email
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send password reset email",
                        recipient=email,
                        error=str(e),
                    )
            else:
                # Provide detailed logging about why password reset was not sent
                if associated_user is None:
                    logger.info(
                        "Password reset requested for non-existent user",
                        email=email,
                    )
                elif not associated_user.is_active:
                    logger.info(
                        "Password reset requested for inactive user",
                        email=email,
                        user_id=associated_user.id,
                    )
                else:
                    # User exists and is active but is_local is False
                    # Check why is_local is False

                    try:
                        sso_settings = GlobalSettings.objects.get(
                            name=GlobalSettings.Names.SSO
                        ).value
                    except GlobalSettings.DoesNotExist:
                        sso_settings = {}

                    sso_enabled = sso_settings.get("is_enabled", False)
                    sso_forced = sso_settings.get("force_sso", False)

                    logger.info(
                        "Password reset requested for non-local user",
                        email=email,
                        user_id=associated_user.id,
                        keep_local_login=associated_user.keep_local_login,
                        sso_enabled=sso_enabled,
                        sso_forced=sso_forced,
                    )
            return Response(status=HTTP_202_ACCEPTED)
        logger.warning("Password reset requested but email server not configured")
        return Response(
            data={
                "error": "Email server not configured, please contact your administrator"
            },
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ResetPasswordConfirmView(views.APIView):
    """
    API Endpoint for reset password confirm
    """

    default_token_generator = PasswordResetTokenGenerator()
    permission_classes = [permissions.AllowAny]
    serialier_class = ResetPasswordConfirmSerializer
    token_generator = default_token_generator

    def get_user(self, uidb64):
        try:
            # urlsafe_base64_decode() decodes to bytestring
            uid = urlsafe_b64decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
        ):
            user = None
        return user

    @method_decorator(ensure_csrf_cookie)
    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uidb64 = serializer.validated_data.get("uidb64")
        token = serializer.validated_data.get("token")
        new_password = serializer.validated_data.get("new_password")
        user = self.get_user(uidb64)
        if (
            user is not None and user.is_local
        ):  # Only local user can reset their password.
            if self.token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response(status=status.HTTP_200_OK)
        return Response(
            data={"error": "The link is invalid or has expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ChangePasswordView(views.APIView):
    """
    An endpoint for changing password.
    """

    permission_classes = (permissions.IsAuthenticated,)

    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.request.user
        old_password = serializer.validated_data.get("old_password")
        new_password = serializer.validated_data.get("new_password")
        if not user.check_password(old_password):
            raise serializers.ValidationError(
                "Your old password was entered incorrectly. Please enter it again."
            )
        user.set_password(new_password)
        user.save()
        return Response(status=status.HTTP_200_OK)


class SetPasswordView(views.APIView):
    """
    An endpoint for setting a password as an administrator.
    """

    permission_classes = (permissions.IsAuthenticated, IsGlobalAdmin)

    serializer_class = SetPasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data.get("new_password")
        user = serializer.validated_data.get("user")
        user.set_password(new_password)
        user.save()
        try:
            email_address = EmailAddress.objects.get(user=user, primary=True)
            email_address.verified = True
            email_address.save()
        except Exception as e:
            logger.error(
                "Error setting email address as verified",
                user=user,
                error=e,
            )
        return Response(status=status.HTTP_200_OK)


class DisableMFAView(views.APIView):
    """
    An endpoint for disabling another user's MFA as an administrator.
    Removes all MFA authenticators (TOTP, WebAuthn, recovery codes).
    The user will need to enable MFA again on their next login.
    """

    permission_classes = (permissions.IsAuthenticated, IsGlobalAdmin)
    serializer_class = DisableMFASerializer

    def post(self, request, *args, **kwargs):
        serializer = DisableMFASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user = serializer.validated_data.get("user")

        # Delete first and branch on the deleted count to avoid an
        # exists-then-delete race where a concurrent request could empty the
        # authenticators between the check and the delete.
        deleted_count, _ = Authenticator.objects.filter(user=target_user).delete()
        if deleted_count > 0:
            logger.warning(
                "Admin disabled MFA for another user",
                admin_id=str(request.user.id),
                admin_email=request.user.email,
                target_user_id=str(target_user.id),
                target_user_email=target_user.email,
                deleted_authenticators=deleted_count,
            )
            return Response(status=status.HTTP_200_OK)

        return Response(
            {"error": "userHasNoMFAEnabled"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class RevokeOtherSessionsView(views.APIView):
    """
    An endpoint for revoking all other user sessions (except the current one).
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header or " " not in auth_header:
            return Response(
                {"error": "Invalid authorization header"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        access_token = auth_header.split(" ")[1]
        digest = crypto.hash_token(access_token)
        user_id = str(request.user.id)

        deleted_count, _ = (
            AuthToken.objects.filter(user_id=user_id)
            .exclude(
                Q(digest=digest)
                | Q(
                    Exists(
                        PersonalAccessToken.objects.filter(auth_token=OuterRef("pk"))
                    )
                )
            )
            .delete()
        )

        return Response(
            {"revoked_sessions": deleted_count},
            status=status.HTTP_200_OK,
        )


class SCIMTokenViewSet(views.APIView):
    """
    GET  /api/iam/scim-token/   — list all SCIM tokens (admin only)
    POST /api/iam/scim-token/   — create a new SCIM token (admin only)
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsGlobalAdmin,
        FeatureFlagRequired,
    ]
    feature_flag = "idp_groups"

    def get(self, request, *args, **kwargs):
        tokens = SCIMToken.objects.select_related("auth_token").all()
        data = [
            {
                "id": t.id,
                "name": t.name,
                "created": t.auth_token.created,
                "digest": t.auth_token.digest,
            }
            for t in tokens
        ]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        name = request.data.get("name") or "SCIM provisioning token"
        if len(name) > 255:
            return Response(
                {"error": "Name must be at most 255 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token_prefix = knox_settings.TOKEN_PREFIX
        with transaction.atomic():
            instance, raw_token = get_token_model().objects.create(
                user=request.user,
                expiry=None,
                prefix=token_prefix,
            )
            scim_token = SCIMToken.objects.create(auth_token=instance, name=name)
        return Response(
            {
                "id": scim_token.id,
                "name": scim_token.name,
                "token": raw_token,
                "created": instance.created,
            },
            status=status.HTTP_201_CREATED,
        )


class SCIMTokenDeleteView(views.APIView):
    """
    DELETE /api/iam/scim-token/{token_id}/  — revoke a SCIM token (admin only)
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsGlobalAdmin,
        FeatureFlagRequired,
    ]
    feature_flag = "idp_groups"

    def delete(self, request, token_id, *args, **kwargs):
        try:
            scim_token = SCIMToken.objects.select_related("auth_token").get(id=token_id)
        except SCIMToken.DoesNotExist:
            return Response(
                {"error": "Token not found."}, status=status.HTTP_404_NOT_FOUND
            )
        scim_token.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

from rest_framework import viewsets
from .models import FeatureToggle

class CanManageFeatureToggles(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, "platform_role", "")
        return role in ["superadmin", "webadmin"]


class FeatureToggleViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Feature Toggles. Accessible by Webadmins, Admins, and Superadmins.
    """
    serializer_class = FeatureToggleSerializer
    queryset = FeatureToggle.objects.all()

    def get_permissions(self):
        if getattr(self, "action", None) in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        return [CanManageFeatureToggles()]

    def list(self, request, *args, **kwargs):
        is_admin_user = request.user.is_superuser or getattr(request.user, "platform_role", "") in ["webadmin", "superadmin"]
        if is_admin_user:
            # Administrators see all toggles to manage and enable feature toggles
            return super().list(request, *args, **kwargs)

        # Standard users see only their active toggles
        qs = self.get_queryset().filter(Q(enabled_for_user=True) | Q(user_exceptions=request.user)).distinct()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

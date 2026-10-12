from django.apps import AppConfig


class IamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "iam"

    def ready(self):
        from django.apps import apps
        from django.db.models.signals import m2m_changed, post_delete

        from iam.cache_builders import (
            invalidate_groups_cache,
            invalidate_assignments_cache,
            invalidate_roles_cache,
        )

        User = apps.get_model("iam", "User")
        RoleAssignment = apps.get_model("iam", "RoleAssignment")
        Role = apps.get_model("iam", "Role")
        IdPGroup = apps.get_model("iam", "IdPGroup")
        FeatureToggle = apps.get_model("iam", "FeatureToggle")

        try:
            from auditlog.registry import auditlog
            if not auditlog.contains(FeatureToggle):
                auditlog.register(FeatureToggle, exclude_fields=["created_at", "updated_at"])
        except Exception:
            pass

        def _user_groups_changed(sender, instance, action, **kwargs):
            if action in {"post_add", "post_remove", "post_clear"}:
                invalidate_groups_cache()
                invalidate_assignments_cache()

        def _ra_perimeters_changed(sender, instance, action, **kwargs):
            if action in {"post_add", "post_remove", "post_clear"}:
                invalidate_assignments_cache()

        def _role_permissions_changed(sender, instance, action, **kwargs):
            if action in {"post_add", "post_remove", "post_clear"}:
                invalidate_roles_cache()

        def _idp_group_membership_changed(sender, instance, action, **kwargs):
            if action in {"post_add", "post_remove", "post_clear"}:
                invalidate_groups_cache()
                invalidate_assignments_cache()

        def _idp_group_deleted(sender, instance, **kwargs):
            invalidate_groups_cache()
            invalidate_assignments_cache()

        m2m_changed.connect(
            _user_groups_changed,
            sender=User.user_groups.through,
            dispatch_uid="iam.user_groups.m2m.invalidate_caches",
            weak=False,
        )
        m2m_changed.connect(
            _ra_perimeters_changed,
            sender=RoleAssignment.perimeter_folders.through,
            dispatch_uid="iam.roleassignment.perimeter_folders.m2m.invalidate_assignments_cache",
            weak=False,
        )
        m2m_changed.connect(
            _role_permissions_changed,
            sender=Role.permissions.through,
            dispatch_uid="iam.role.permissions.m2m.invalidate_roles_cache",
            weak=False,
        )
        m2m_changed.connect(
            _idp_group_membership_changed,
            sender=User.idp_groups.through,
            dispatch_uid="iam.user.idp_groups.m2m.invalidate_caches",
            weak=False,
        )
        m2m_changed.connect(
            _idp_group_membership_changed,
            sender=IdPGroup.user_groups.through,
            dispatch_uid="iam.idpgroup.user_groups.m2m.invalidate_caches",
            weak=False,
        )
        post_delete.connect(
            _idp_group_deleted,
            sender=IdPGroup,
            dispatch_uid="iam.idpgroup.post_delete.invalidate_caches",
            weak=False,
        )

        from django.contrib.auth.signals import user_logged_out
        def _on_user_logged_out(sender, request, user, **kwargs):
            if not user or not getattr(user, 'is_authenticated', False):
                return
            try:
                from auditlog.models import LogEntry
                from django.contrib.contenttypes.models import ContentType
                import json
                LogEntry.objects.create(
                    content_type=ContentType.objects.get_for_model(user),
                    object_pk=str(user.pk),
                    object_id=user.pk,
                    object_repr=getattr(user, "email", str(user)),
                    action=LogEntry.Action.ACCESS,
                    actor=user,
                    changes=json.dumps({"event": "logout", "logout": True, "email": getattr(user, 'email', str(user))})
                )
            except Exception:
                pass

        user_logged_out.connect(
            _on_user_logged_out,
            dispatch_uid="iam.user_logged_out.audit_log",
            weak=False,
        )

from django.apps import AppConfig
from django.db.models.signals import post_migrate
import os

from .startup import startup


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        import core.webhooks
        import core.signals
        import core.mappings.signals

        try:
            from auditlog.registry import auditlog
            from iam.models import FeatureToggle
            if not auditlog.contains(FeatureToggle):
                auditlog.register(FeatureToggle, exclude_fields=["created_at", "updated_at"])
        except Exception:
            pass

        # avoid post_migrate handler if we are in the main, as it interferes with restore
        if not os.environ.get("RUN_MAIN"):
            # No sender filter: startup() waits for the last app's
            # post_migrate so all permission rows exist before .set().
            post_migrate.connect(startup)

        # Start background escalation worker for automated triggers
        import sys
        is_management_cmd = any(cmd in sys.argv for cmd in ["migrate", "makemigrations", "test", "shell", "collectstatic"])
        if not is_management_cmd:
            try:
                from core.escalation_engine import start_escalation_background_worker
                start_escalation_background_worker()
            except Exception as e:
                print(f"Failed to start escalation worker: {e}")

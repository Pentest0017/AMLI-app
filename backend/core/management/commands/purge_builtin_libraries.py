import structlog
from django.core.management.base import BaseCommand
from core.models import StoredLibrary, LoadedLibrary, Framework

logger = structlog.getLogger(__name__)


class Command(BaseCommand):
    help = "Purge all builtin and preloaded libraries and frameworks"

    def handle(self, *args, **options):
        try:
            stored_count = StoredLibrary.objects.all().delete()[0]
            loaded_count = LoadedLibrary.objects.all().delete()[0]
            framework_count = Framework.objects.all().delete()[0]

            logger.info(
                "Successfully purged builtin libraries",
                deleted_stored=stored_count,
                deleted_loaded=loaded_count,
                deleted_frameworks=framework_count,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Purged {stored_count} stored libraries, {loaded_count} loaded libraries, {framework_count} frameworks."
                )
            )
        except Exception as e:
            logger.error("Failed to purge builtin libraries", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Error purging builtin libraries: {e}"))

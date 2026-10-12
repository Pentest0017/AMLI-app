from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0127_remove_appliedcontrol_new_owner_and_more"),
        ("ebios_rm", "0022_ebiosrmstudy_new_authors_ebiosrmstudy_new_reviewers"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="ebiosrmstudy",
                    name="authors",
                ),
                migrations.RemoveField(
                    model_name="ebiosrmstudy",
                    name="reviewers",
                ),
                migrations.RenameField(
                    model_name="ebiosrmstudy",
                    old_name="new_authors",
                    new_name="authors",
                ),
                migrations.RenameField(
                    model_name="ebiosrmstudy",
                    old_name="new_reviewers",
                    new_name="reviewers",
                ),
                migrations.AlterField(
                    model_name="ebiosrmstudy",
                    name="authors",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="ebios_rm_study_authors",
                        to="core.actor",
                        verbose_name="Authors",
                    ),
                ),
                migrations.AlterField(
                    model_name="ebiosrmstudy",
                    name="reviewers",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="ebios_rm_study_reviewers",
                        to="core.actor",
                        verbose_name="Reviewers",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

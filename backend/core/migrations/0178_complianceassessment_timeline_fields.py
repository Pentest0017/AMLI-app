from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0177_remove_presetjourneystep_journey_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="complianceassessment",
            name="start_date",
            field=models.DateField(blank=True, null=True, verbose_name="Start date"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="evidence_due_date",
            field=models.DateField(blank=True, null=True, verbose_name="Evidence due date"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="audit_period_year",
            field=models.IntegerField(blank=True, null=True, verbose_name="Audit period year"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="selected_nodes",
            field=models.JSONField(blank=True, null=True, verbose_name="Selected requirement nodes"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="selected_domains",
            field=models.JSONField(blank=True, null=True, verbose_name="Selected domains"),
        ),
        migrations.AddField(
            model_name="complianceassessment",
            name="schedule_type",
            field=models.CharField(
                choices=[("on_demand", "On-Demand"), ("scheduled", "Scheduled")],
                default="on_demand",
                max_length=20,
                verbose_name="Schedule type",
            ),
        ),
    ]

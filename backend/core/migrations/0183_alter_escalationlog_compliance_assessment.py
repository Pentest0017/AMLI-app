import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0182_control_assignment_evidence_escalation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='escalationlog',
            name='compliance_assessment',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='escalation_logs',
                to='core.complianceassessment',
            ),
        ),
    ]

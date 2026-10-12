from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0178_complianceassessment_timeline_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='complianceassessment',
            name='scope_mode',
            field=models.CharField(
                choices=[('full', 'Full Framework'), ('custom', 'Custom Scope')],
                default='full',
                max_length=20,
                verbose_name='Scope mode'
            ),
        ),
        migrations.AlterField(
            model_name='complianceassessment',
            name='framework',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='core.framework',
                verbose_name='Framework'
            ),
        ),
    ]

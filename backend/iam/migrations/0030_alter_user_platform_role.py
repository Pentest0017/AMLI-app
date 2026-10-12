from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iam', '0029_featuretoggle_enabled_for_web_admin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='platform_role',
            field=models.CharField(
                choices=[
                    ('superadmin', 'Superadmin'),
                    ('webadmin', 'Webadmin'),
                    ('admin', 'Admin'),
                    ('auditor', 'Auditor'),
                    ('user', 'User'),
                ],
                default='user',
                max_length=50,
                verbose_name='Platform Role',
            ),
        ),
    ]

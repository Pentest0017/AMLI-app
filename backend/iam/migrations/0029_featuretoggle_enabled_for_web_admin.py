from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iam', '0028_user_reports_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='featuretoggle',
            name='enabled_for_web_admin',
            field=models.BooleanField(default=True, verbose_name='Enabled for Web Admin'),
        ),
    ]

# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_allow_blank_account_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='language',
            field=models.CharField(
                max_length=5,
                default='en',
                choices=[('en', 'English'), ('dv', 'Dhivehi')]
            ),
        ),
    ]

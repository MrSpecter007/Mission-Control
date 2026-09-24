from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platforms', '0005_monitored_url_health_results'),
    ]

    operations = [
        migrations.AddField(
            model_name='healthcheck',
            name='homepage_preview',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platforms', '0007_platformcredential'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('activity_type', models.CharField(
                    choices=[
                        ('development', 'Development'),
                        ('deployment', 'Deployment'),
                        ('infrastructure', 'Infrastructure'),
                        ('configuration', 'Configuration'),
                        ('maintenance', 'Maintenance'),
                        ('content', 'Content'),
                        ('operations', 'Operations'),
                        ('decision', 'Decision'),
                        ('incident', 'Incident'),
                        ('milestone', 'Milestone'),
                        ('other', 'Other'),
                    ],
                    default='other',
                    max_length=20,
                )),
                ('occurred_at', models.DateTimeField()),
                ('is_milestone', models.BooleanField(default=False)),
                ('ref_url', models.URLField(blank=True, help_text='Commit, PR, or external reference URL')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('platform', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activity_entries',
                    to='platforms.platform',
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activity_entries',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'activity entry',
                'verbose_name_plural': 'activity entries',
                'ordering': ['-occurred_at'],
            },
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('platforms', '0006_healthcheck_homepage_preview'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=200)),
                ('kind', models.CharField(
                    choices=[
                        ('admin_panel', 'Admin panel'),
                        ('hosting', 'Hosting panel'),
                        ('ssh', 'SSH / Server'),
                        ('ftp', 'FTP / SFTP'),
                        ('database', 'Database'),
                        ('api', 'API key'),
                        ('other', 'Other'),
                    ],
                    default='admin_panel',
                    max_length=20,
                )),
                ('url', models.URLField(blank=True)),
                ('username', models.CharField(blank=True, max_length=200)),
                ('password_encrypted', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('platform', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='credentials',
                    to='platforms.platform',
                )),
            ],
            options={
                'ordering': ['kind', 'label'],
            },
        ),
    ]

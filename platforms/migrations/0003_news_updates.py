from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('platforms', '0002_add_framework_oscar_other'),
    ]

    operations = [
        migrations.CreateModel(
            name='FrameworkVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('framework', models.CharField(max_length=30, unique=True)),
                ('latest_version', models.CharField(blank=True, max_length=50)),
                ('release_url', models.URLField(blank=True)),
                ('checked_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='NewsItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='news_items', to='platforms.platform',
                )),
                ('source_type', models.CharField(
                    choices=[
                        ('github_commit', 'GitHub Commits'),
                        ('github_release', 'GitHub Release'),
                        ('framework_release', 'Framework Release'),
                        ('health_event', 'Health Event'),
                        ('deployment_lag', 'Deployment Lag'),
                        ('dependency_outdated', 'Dependency Outdated'),
                    ],
                    max_length=30,
                )),
                ('title', models.CharField(max_length=500)),
                ('body', models.TextField(blank=True)),
                ('url', models.URLField(blank=True)),
                ('published_at', models.DateTimeField()),
                ('fetched_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('source_ref', models.CharField(blank=True, max_length=200)),
                ('framework', models.CharField(blank=True, max_length=30)),
            ],
            options={
                'ordering': ['-published_at'],
            },
        ),
        migrations.CreateModel(
            name='RepositoryState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('repository', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='state', to='platforms.repository',
                )),
                ('last_checked_sha', models.CharField(blank=True, max_length=40)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('last_deployed_sha', models.CharField(blank=True, max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name='DependencySnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('repository', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dependency_snapshots', to='platforms.repository',
                )),
                ('manifest_path', models.CharField(max_length=200)),
                ('manifest_sha', models.CharField(blank=True, max_length=40)),
                ('ecosystem', models.CharField(blank=True, max_length=20)),
                ('dependencies', models.JSONField(default=list)),
                ('scanned_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'unique_together': {('repository', 'manifest_path')},
            },
        ),
    ]

"""
Load demo data representing representative platforms.
Usage: python manage.py seed_demo [--flush]
"""
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from platforms.models import (
    Platform, Repository, Host, Service, Domain, Deployment, HealthCheck,
    PlatformType, FrameworkChoice, LifecycleStatus, EnvironmentChoice,
    HostProvider, HostType, RepoProvider, ServiceType, DeploymentStatus, HealthStatus,
)


class Command(BaseCommand):
    help = 'Load demo data for Mission Control'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true', help='Remove existing demo data first')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            Platform.objects.all().delete()
            Host.objects.all().delete()
            self.stdout.write('Flushed existing data.')

        now = datetime.now(tz=timezone.utc)

        # Shared hosts
        do_host = Host.objects.get_or_create(
            name='DigitalOcean Production',
            defaults=dict(
                provider=HostProvider.DIGITALOCEAN,
                hostname='prod.catalystdv.com',
                environment=EnvironmentChoice.PRODUCTION,
                host_type=HostType.VPS,
                os_info='Ubuntu 24.04',
                status='active',
            )
        )[0]

        dev_host = Host.objects.get_or_create(
            name='Development Server',
            defaults=dict(
                provider=HostProvider.CUSTOM,
                hostname='dev.internal',
                environment=EnvironmentChoice.DEVELOPMENT,
                host_type=HostType.VPS,
                status='active',
            )
        )[0]

        demo_platforms = [
            dict(
                name='Catalystdev',
                slug='catalystdev',
                description='Main Catalyst development services website.',
                platform_type=PlatformType.WEBSITE,
                framework=FrameworkChoice.WAGTAIL,
                lifecycle_status=LifecycleStatus.ACTIVE,
                default_environment=EnvironmentChoice.PRODUCTION,
                repo=dict(name='catalystdev-website', provider=RepoProvider.GITHUB, url='https://github.com/catalystdv/catalystdev', branch='main'),
                host=do_host,
                domains=[
                    dict(hostname='catalystdev.com', is_primary=True, ssl_enabled=True, environment=EnvironmentChoice.PRODUCTION),
                    dict(hostname='www.catalystdev.com', is_primary=False, ssl_enabled=True, environment=EnvironmentChoice.PRODUCTION),
                ],
                service=dict(name='Wagtail Application', service_type=ServiceType.WEB, environment=EnvironmentChoice.PRODUCTION),
                health=HealthStatus.HEALTHY,
                deploy_version='v2.4.1',
            ),
            dict(
                name='Pound It',
                slug='pound-it',
                description='Workout tracking web application.',
                platform_type=PlatformType.WEB_APPLICATION,
                framework=FrameworkChoice.DJANGO,
                lifecycle_status=LifecycleStatus.ACTIVE,
                default_environment=EnvironmentChoice.PRODUCTION,
                repo=dict(name='pound-it-app', provider=RepoProvider.GITHUB, url='https://github.com/catalystdv/pound-it', branch='main'),
                host=do_host,
                domains=[
                    dict(hostname='poundit.app', is_primary=True, ssl_enabled=True, environment=EnvironmentChoice.PRODUCTION),
                ],
                service=dict(name='Django Application', service_type=ServiceType.WEB, environment=EnvironmentChoice.PRODUCTION),
                health=HealthStatus.HEALTHY,
                deploy_version='v1.9.0',
            ),
            dict(
                name='Specter Parts',
                slug='specter-parts',
                description='E-commerce store for performance automotive parts.',
                platform_type=PlatformType.ECOMMERCE,
                framework=FrameworkChoice.WORDPRESS,
                lifecycle_status=LifecycleStatus.ACTIVE,
                default_environment=EnvironmentChoice.PRODUCTION,
                repo=None,
                host=do_host,
                domains=[
                    dict(hostname='specterparts.com', is_primary=True, ssl_enabled=True, environment=EnvironmentChoice.PRODUCTION),
                ],
                service=dict(name='WordPress Application', service_type=ServiceType.WEB, environment=EnvironmentChoice.PRODUCTION),
                health=HealthStatus.UNKNOWN,
                deploy_version=None,
            ),
            dict(
                name='Estrella',
                slug='estrella',
                description='Restaurant website and ordering platform.',
                platform_type=PlatformType.WEBSITE,
                framework=FrameworkChoice.LARAVEL,
                lifecycle_status=LifecycleStatus.DEVELOPMENT,
                default_environment=EnvironmentChoice.DEVELOPMENT,
                repo=dict(name='estrella-site', provider=RepoProvider.GITHUB, url='https://github.com/catalystdv/estrella', branch='develop'),
                host=dev_host,
                domains=[],
                service=dict(name='Laravel Application', service_type=ServiceType.WEB, environment=EnvironmentChoice.DEVELOPMENT),
                health=None,
                deploy_version=None,
            ),
        ]

        for pdata in demo_platforms:
            p, created = Platform.objects.get_or_create(
                slug=pdata['slug'],
                defaults=dict(
                    name=pdata['name'],
                    description=pdata['description'],
                    platform_type=pdata['platform_type'],
                    framework=pdata['framework'],
                    lifecycle_status=pdata['lifecycle_status'],
                    default_environment=pdata['default_environment'],
                )
            )
            action = 'Created' if created else 'Skipped (exists)'
            self.stdout.write(f'{action}: {p.name}')

            if not created:
                continue

            # Repo
            if pdata['repo']:
                r = pdata['repo']
                Repository.objects.create(
                    platform=p,
                    name=r['name'],
                    provider=r['provider'],
                    url=r['url'],
                    default_branch=r['branch'],
                )

            # Domains
            for d in pdata['domains']:
                Domain.objects.create(platform=p, **d)

            # Service
            svc = None
            if pdata['service']:
                s = pdata['service']
                svc = Service.objects.create(platform=p, host=pdata['host'], **s)

            # Deployment
            if pdata['deploy_version']:
                Deployment.objects.create(
                    platform=p,
                    service=svc,
                    environment=EnvironmentChoice.PRODUCTION,
                    version=pdata['deploy_version'],
                    status=DeploymentStatus.SUCCESS,
                    deployed_at=now - timedelta(days=3),
                    deployed_by='deploy-bot',
                )

            # Health check
            if pdata['health']:
                endpoint = ''
                domain = p.primary_domain
                if domain:
                    endpoint = domain.url
                HealthCheck.objects.create(
                    platform=p,
                    service=svc,
                    endpoint=endpoint,
                    status=pdata['health'],
                    http_status=200 if pdata['health'] == HealthStatus.HEALTHY else None,
                    response_time_ms=142.3 if pdata['health'] == HealthStatus.HEALTHY else None,
                    checked_at=now - timedelta(hours=1),
                )

        self.stdout.write(self.style.SUCCESS('Demo data loaded.'))

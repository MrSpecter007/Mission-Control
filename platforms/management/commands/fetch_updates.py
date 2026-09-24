import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetch technology updates from GitHub, package registries, and health checks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            metavar='SLUG',
            help='Run only for this platform slug',
        )
        parser.add_argument(
            '--source',
            choices=['github', 'frameworks', 'dependencies', 'health'],
            help='Run only one source type',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and print without saving anything',
        )

    def handle(self, *args, **options):
        from platforms.updater.runner import run_all

        platform_slug = options.get('platform')
        source = options.get('source')
        dry_run = options.get('dry_run', False)

        parts = [
            f'source={source or "all"}',
            f'platform={platform_slug or "all"}',
        ]
        if dry_run:
            parts.append('DRY RUN')

        self.stdout.write(f'fetch_updates: {", ".join(parts)}')

        stats = run_all(
            platform_slug=platform_slug,
            source=source,
            dry_run=dry_run,
        )

        msg = (
            f'Done — created: {stats["created"]}, '
            f'skipped: {stats["skipped"]}, '
            f'errors: {stats["errors"]}'
        )
        self.stdout.write(self.style.SUCCESS(msg))
        if stats['errors']:
            self.stderr.write(f'{stats["errors"]} error(s) — check logs for details')

import logging
import os

from platforms.models import NewsItem, Platform

from .dependencies import fetch_dependency_updates
from .frameworks import fetch_framework_releases
from .github import fetch_github_activity
from .health_events import fetch_health_events
from .wordpress import fetch_wordpress_releases
from .wordpress_plugins import fetch_wordpress_plugin_updates

logger = logging.getLogger(__name__)


def run_all(
    platform_slug: str = None,
    source: str = None,
    dry_run: bool = False,
) -> dict:
    token = os.environ.get('GITHUB_TOKEN') or None
    stats = {'created': 0, 'skipped': 0, 'errors': 0}

    qs = Platform.objects.all()
    if platform_slug:
        qs = qs.filter(slug=platform_slug)
    platforms = list(qs.prefetch_related('repositories', 'health_checks', 'deployments'))

    run_github = source in (None, 'github')
    run_frameworks = source in (None, 'frameworks')
    run_deps = source in (None, 'dependencies')
    run_health = source in (None, 'health')

    all_items = []
    registry_cache = {}  # shared across repos to deduplicate registry calls

    for platform in platforms:
        repos = [
            r for r in platform.repositories.all()
            if r.status == 'active' and r.url and 'github.com' in r.url
        ]

        if run_github:
            for repo in repos:
                try:
                    items = fetch_github_activity(repo, token=token, dry_run=dry_run)
                    all_items.extend(items)
                    if items:
                        logger.info('GitHub: %d item(s) for %s', len(items), repo.name)
                except Exception:
                    logger.exception('Error in GitHub fetcher for %s', repo.name)
                    stats['errors'] += 1

        if run_deps:
            for repo in repos:
                try:
                    items = fetch_dependency_updates(
                        repo, token=token, dry_run=dry_run,
                        registry_cache=registry_cache,
                    )
                    all_items.extend(items)
                    if items:
                        logger.info('Dependencies: %d item(s) for %s', len(items), repo.name)
                except Exception:
                    logger.exception('Error in dependency fetcher for %s', repo.name)
                    stats['errors'] += 1

            if platform.framework == 'wordpress':
                for repo in repos:
                    try:
                        items = fetch_wordpress_plugin_updates(repo, token=token, dry_run=dry_run)
                        all_items.extend(items)
                        if items:
                            logger.info('WP plugins: %d item(s) for %s', len(items), repo.name)
                    except Exception:
                        logger.exception('Error in WP plugin fetcher for %s', repo.name)
                        stats['errors'] += 1

        if run_health:
            try:
                items = fetch_health_events(platform, dry_run=dry_run)
                all_items.extend(items)
            except Exception:
                logger.exception('Error in health fetcher for %s', platform.name)
                stats['errors'] += 1

    if run_frameworks:
        try:
            items = fetch_framework_releases(token=token, dry_run=dry_run)
            all_items.extend(items)
            if items:
                logger.info('Frameworks: %d item(s)', len(items))
        except Exception:
            logger.exception('Error in framework fetcher')
            stats['errors'] += 1

        try:
            items = fetch_wordpress_releases(dry_run=dry_run)
            all_items.extend(items)
            if items:
                logger.info('WordPress: %d item(s)', len(items))
        except Exception:
            logger.exception('Error in WordPress release fetcher')
            stats['errors'] += 1

    if not dry_run:
        for item_dict in all_items:
            try:
                NewsItem.objects.create(**item_dict)
                stats['created'] += 1
            except Exception:
                logger.debug('Skipping (likely duplicate): %s', item_dict.get('title'))
                stats['skipped'] += 1
    else:
        stats['created'] = len(all_items)

    return stats

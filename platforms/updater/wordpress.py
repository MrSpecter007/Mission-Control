import logging
from datetime import datetime, timezone

import requests

from platforms.models import FrameworkVersion, NewsItem, NewsItemSourceType, Platform

logger = logging.getLogger(__name__)
WP_API = 'https://api.wordpress.org/core/version-check/1.7/'
RELEASE_PAGE = 'https://wordpress.org/news/category/releases/'


def fetch_wordpress_releases(dry_run=False) -> list:
    """
    Check wordpress.org for the latest stable WP core release and emit a
    per-platform NewsItem for every active WordPress platform that hasn't
    already seen this version.
    """
    wp_platforms = list(
        Platform.objects.filter(framework='wordpress').exclude(lifecycle_status='archived')
    )
    if not wp_platforms:
        return []

    try:
        r = requests.get(WP_API, timeout=10, headers={'User-Agent': 'MissionControl/1.0'})
        r.raise_for_status()
        data = r.json()
    except Exception:
        logger.exception('Failed to fetch WordPress releases from wordpress.org')
        return []

    offers = data.get('offers', [])
    # 'upgrade' response = a new version is available; fall back to first offer
    stable = next((o for o in offers if o.get('response') == 'upgrade'), None) or (offers[0] if offers else None)
    if not stable:
        return []

    version = stable.get('version', '').strip()
    if not version:
        return []

    fv, _ = FrameworkVersion.objects.get_or_create(
        framework='wordpress',
        defaults={'latest_version': '', 'release_url': RELEASE_PAGE},
    )

    if fv.latest_version == version:
        if not dry_run:
            fv.checked_at = datetime.now(tz=timezone.utc)
            fv.save(update_fields=['checked_at'])
        return []

    if not dry_run:
        fv.latest_version = version
        fv.release_url = RELEASE_PAGE
        fv.checked_at = datetime.now(tz=timezone.utc)
        fv.save()

    now = datetime.now(tz=timezone.utc)
    items = []
    for platform in wp_platforms:
        source_ref = f'wordpress:{version}:{platform.slug}'
        if NewsItem.objects.filter(
            platform=platform,
            source_type=NewsItemSourceType.FRAMEWORK_RELEASE,
            source_ref=source_ref,
        ).exists():
            continue
        items.append({
            'platform': platform,
            'source_type': NewsItemSourceType.FRAMEWORK_RELEASE,
            'title': f'WordPress {version} available',
            'body': f'WordPress core {version} has been released. Review the changelog and schedule an update.',
            'url': RELEASE_PAGE,
            'published_at': now,
            'source_ref': source_ref,
            'framework': 'wordpress',
        })

    return items

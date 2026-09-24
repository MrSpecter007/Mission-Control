import logging
from datetime import datetime, timezone

import requests

from platforms.models import FrameworkVersion, NewsItem, NewsItemSourceType, Platform

logger = logging.getLogger(__name__)
GITHUB_API = 'https://api.github.com'

FRAMEWORK_REPOS = {
    'django':    ('django', 'django'),
    'wagtail':   ('wagtail', 'wagtail'),
    'laravel':   ('laravel', 'laravel'),
    'oscar':     ('django-oscar', 'django-oscar'),
    # wordpress handled separately via wordpress.org API (not GitHub releases)
}

FRAMEWORK_DISPLAY = {
    'django':    'Django',
    'wagtail':   'Wagtail',
    'wordpress': 'WordPress',
    'laravel':   'Laravel',
    'oscar':     'Oscar',
}


def _headers(token=None):
    h = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MissionControl/1.0',
    }
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return datetime.now(tz=timezone.utc)


def fetch_framework_releases(token=None, dry_run=False) -> list:
    active_frameworks = set(
        Platform.objects.values_list('framework', flat=True).distinct()
    )
    items = []
    for framework, (owner, repo) in FRAMEWORK_REPOS.items():
        if framework not in active_frameworks:
            continue
        try:
            items.extend(_check_framework(framework, owner, repo, token, dry_run))
        except Exception:
            logger.exception('Error checking framework releases for %s', framework)
    return items


def _check_framework(framework: str, owner: str, repo: str, token, dry_run: bool) -> list:
    try:
        r = requests.get(
            f'{GITHUB_API}/repos/{owner}/{repo}/releases/latest',
            headers=_headers(token), timeout=10,
        )
    except Exception:
        logger.exception('HTTP error fetching release for %s', framework)
        return []

    if r.status_code != 200:
        return []

    data = r.json()
    tag = data.get('tag_name', '')
    if not tag:
        return []

    tag_clean = tag.lstrip('v')
    release_url = data.get('html_url', '')
    pub = _parse_dt(data.get('published_at') or '')

    fv, _ = FrameworkVersion.objects.get_or_create(
        framework=framework,
        defaults={'latest_version': '', 'release_url': ''},
    )

    if fv.latest_version == tag_clean:
        if not dry_run:
            fv.checked_at = datetime.now(tz=timezone.utc)
            fv.save(update_fields=['checked_at'])
        return []

    source_ref = f'{framework}:{tag}'
    already_exists = NewsItem.objects.filter(
        platform__isnull=True,
        source_type=NewsItemSourceType.FRAMEWORK_RELEASE,
        source_ref=source_ref,
    ).exists()

    if not dry_run:
        fv.latest_version = tag_clean
        fv.release_url = release_url
        fv.checked_at = datetime.now(tz=timezone.utc)
        fv.save()

    if already_exists:
        return []

    return [{
        'platform': None,
        'source_type': NewsItemSourceType.FRAMEWORK_RELEASE,
        'title': f'{FRAMEWORK_DISPLAY.get(framework, framework.title())} {tag_clean} released',
        'body': (data.get('body') or '')[:500],
        'url': release_url,
        'published_at': pub,
        'source_ref': source_ref,
        'framework': framework,
    }]

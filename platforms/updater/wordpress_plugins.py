"""Scan wp-content/plugins/ via GitHub and check wordpress.org for updates."""
import logging
import re
from datetime import datetime, timezone

import requests

from platforms.models import DependencySnapshot, NewsItem, NewsItemSourceType, Repository

logger = logging.getLogger(__name__)
GITHUB_API = 'https://api.github.com'
WP_PLUGIN_API = 'https://api.wordpress.org/plugins/info/1.2/'

_NAME_RE = re.compile(r'Plugin Name:\s*(.+)', re.IGNORECASE)
_VER_RE = re.compile(r'^\s*\*?\s*Version:\s*([0-9][^\s,;*]+)', re.IGNORECASE | re.MULTILINE)
_CLOSED_REASONS = {
    'security-issue': 'Closed: security issue',
    'guideline-violation': 'Closed: guideline violation',
    'author-request': 'Closed by author request',
    'merged': 'Merged into another plugin',
}


def _gh_headers(token=None):
    h = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MissionControl/1.0',
    }
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def _parse_owner_repo(url: str):
    m = re.search(r'github\.com[/:]([^/]+)/([^/\.]+)', url or '')
    return (m.group(1), m.group(2)) if m else None


def _parse_major(v: str):
    try:
        return int(re.sub(r'[^0-9\.]', '', v.lstrip('v')).split('.')[0])
    except (ValueError, AttributeError):
        return None


def _list_plugin_dirs(owner, repo, token) -> list[str]:
    try:
        r = requests.get(
            f'{GITHUB_API}/repos/{owner}/{repo}/contents/wp-content/plugins',
            headers=_gh_headers(token), timeout=10,
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return [item['name'] for item in r.json() if item.get('type') == 'dir']
    except Exception:
        logger.exception('Error listing plugins for %s/%s', owner, repo)
        return []


def _read_plugin_header(owner, repo, plugin_slug, token) -> tuple[str, str]:
    """Return (display_name, installed_version) from the plugin PHP header."""
    raw_header = _gh_headers(token).copy()
    raw_header['Accept'] = 'application/vnd.github.raw+json'

    # Try <slug>/<slug>.php first, then scan for any .php in the dir
    candidates = [f'wp-content/plugins/{plugin_slug}/{plugin_slug}.php']
    try:
        r = requests.get(
            f'{GITHUB_API}/repos/{owner}/{repo}/contents/wp-content/plugins/{plugin_slug}',
            headers=_gh_headers(token), timeout=10,
        )
        if r.status_code == 200:
            php_files = [f['path'] for f in r.json() if f.get('name', '').endswith('.php') and f.get('type') == 'file']
            candidates = php_files[:5]  # check up to 5
    except Exception:
        pass

    for path in candidates:
        try:
            r = requests.get(
                f'{GITHUB_API}/repos/{owner}/{repo}/contents/{path}',
                headers=raw_header, timeout=10,
            )
            if r.status_code != 200:
                continue
            head = r.text[:3000]
            name_m = _NAME_RE.search(head)
            ver_m = _VER_RE.search(head)
            if name_m or ver_m:
                name = name_m.group(1).strip() if name_m else plugin_slug
                version = ver_m.group(1).strip() if ver_m else ''
                return name, version
        except Exception:
            continue

    return plugin_slug, ''


def _wp_plugin_info(plugin_slug: str) -> tuple[str, bool, str]:
    """Query wordpress.org. Returns (latest_version, is_closed, closed_reason)."""
    try:
        r = requests.get(
            WP_PLUGIN_API,
            params={
                'action': 'plugin_information',
                'request[slug]': plugin_slug,
                'request[fields][versions]': '0',
                'request[fields][sections]': '0',
            },
            timeout=10,
            headers={'User-Agent': 'MissionControl/1.0'},
        )
        if r.status_code != 200:
            return '', False, ''
        data = r.json()
        if not isinstance(data, dict) or 'error' in data:
            return '', False, ''
        version = data.get('version', '')
        closed = bool(data.get('closed', False))
        reason = _CLOSED_REASONS.get(data.get('closed_reason', ''), 'Removed from WordPress.org') if closed else ''
        return version, closed, reason
    except Exception:
        logger.exception('Error querying wordpress.org for plugin %s', plugin_slug)
        return '', False, ''


def fetch_wordpress_plugin_updates(repository: Repository, token=None, dry_run=False) -> list:
    """Scan plugins/, compare with wordpress.org, update snapshot, emit NewsItems."""
    parsed = _parse_owner_repo(repository.url)
    if not parsed:
        return []
    owner, repo_name = parsed
    platform = repository.platform
    now = datetime.now(tz=timezone.utc)

    plugin_dirs = _list_plugin_dirs(owner, repo_name, token)
    if not plugin_dirs:
        return []

    dep_records = []
    news_items = []

    for slug in plugin_dirs:
        display_name, installed_version = _read_plugin_header(owner, repo_name, slug, token)
        latest_version, is_closed, closed_reason = _wp_plugin_info(slug)

        pinned_major = _parse_major(installed_version)
        latest_major = _parse_major(latest_version) if latest_version else None
        is_major_outdated = (
            pinned_major is not None
            and latest_major is not None
            and latest_major > pinned_major
        )

        dep_records.append({
            'name': display_name,
            'slug': slug,
            'pinned_version': installed_version,
            'latest_version': latest_version,
            'latest_major': latest_major,
            'is_major_outdated': is_major_outdated,
            'is_deprecated': is_closed,
            'deprecated_reason': closed_reason,
        })

        if not installed_version:
            continue

        # Closed / removed from wordpress.org
        if is_closed:
            src_ref = f'{slug}:deprecated'
            if not NewsItem.objects.filter(
                platform=platform,
                source_type=NewsItemSourceType.DEPENDENCY_OUTDATED,
                source_ref=src_ref,
            ).exists():
                news_items.append({
                    'platform': platform,
                    'source_type': NewsItemSourceType.DEPENDENCY_OUTDATED,
                    'title': f'Plugin {display_name} removed from WordPress.org',
                    'body': closed_reason,
                    'url': f'https://wordpress.org/plugins/{slug}/',
                    'published_at': now,
                    'source_ref': src_ref,
                    'framework': 'wordpress',
                })
            continue

        if not latest_version or not is_major_outdated:
            # Check minor update too
            try:
                p = [int(x) for x in installed_version.split('.')]
                l = [int(x) for x in latest_version.split('.')]
                if p >= l:
                    continue
            except (ValueError, AttributeError):
                continue

        src_ref = f'{slug}:{latest_version}'
        if NewsItem.objects.filter(
            platform=platform,
            source_type=NewsItemSourceType.DEPENDENCY_OUTDATED,
            source_ref=src_ref,
        ).exists():
            continue

        kind = 'Major' if is_major_outdated else 'Update'
        news_items.append({
            'platform': platform,
            'source_type': NewsItemSourceType.DEPENDENCY_OUTDATED,
            'title': f'Plugin {display_name} {latest_version} available (installed: {installed_version})',
            'body': f'{kind} update available. Repository: {repository.name}.',
            'url': f'https://wordpress.org/plugins/{slug}/',
            'published_at': now,
            'source_ref': src_ref,
            'framework': 'wordpress',
        })

    if dep_records and not dry_run:
        snapshot, _ = DependencySnapshot.objects.get_or_create(
            repository=repository,
            manifest_path='wp-content/plugins/',
            defaults={'ecosystem': 'wordpress', 'dependencies': []},
        )
        snapshot.ecosystem = 'wordpress'
        snapshot.dependencies = dep_records
        snapshot.scanned_at = now
        snapshot.save()

    return news_items

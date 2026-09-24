import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests

from platforms.models import DependencySnapshot, NewsItem, NewsItemSourceType, Repository

logger = logging.getLogger(__name__)
GITHUB_API = 'https://api.github.com'

MANIFEST_FILES = [
    ('requirements.txt', 'pypi'),
    ('pyproject.toml', 'pypi'),
    ('package.json', 'npm'),
    ('composer.json', 'packagist'),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _github_headers(token=None):
    h = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MissionControl/1.0',
    }
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def _parse_owner_repo(url: str):
    if not url:
        return None
    m = re.search(r'github\.com[/:]([^/]+)/([^/\.]+)', url)
    return (m.group(1), m.group(2)) if m else None


def _parse_major(version_str: str) -> Optional[int]:
    if not version_str:
        return None
    clean = re.sub(r'[^0-9\.]', '', version_str.lstrip('v')).split('.')[0]
    try:
        return int(clean)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Manifest parsers
# ---------------------------------------------------------------------------

def _parse_requirements_txt(content: str) -> dict:
    deps = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '-', 'http', 'git+')):
            continue
        line = re.sub(r'\[.*?\]', '', line)  # strip extras
        m = re.match(r'^([A-Za-z0-9_\-\.]+)\s*[=~<>!]+\s*([\d][^\s,;]*)', line)
        if m:
            name = m.group(1).lower().replace('_', '-')
            version = re.sub(r'[^0-9\.]', '', m.group(2).split(',')[0])
            if version:
                deps[name] = version
    return deps


def _parse_pyproject_toml(content: str) -> dict:
    deps = {}
    in_project = False
    in_poetry_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == '[project]':
            in_project, in_poetry_deps = True, False
            continue
        if stripped == '[tool.poetry.dependencies]':
            in_project, in_poetry_deps = False, True
            continue
        if stripped.startswith('[') and stripped not in ('[project]', '[tool.poetry.dependencies]'):
            in_project, in_poetry_deps = False, False
            continue

        if in_project and stripped.startswith('"') and not stripped.startswith('#'):
            # PEP 631 inline: "django>=4.2"
            m = re.match(r'"([A-Za-z0-9_\-\.]+)[>=<~!]+\s*([\d][^"]*)"', stripped)
            if m:
                name = m.group(1).lower().replace('_', '-')
                version = re.sub(r'[^0-9\.]', '', m.group(2).split(',')[0])
                if version:
                    deps[name] = version

        if in_poetry_deps and '=' in stripped and not stripped.startswith('#'):
            m = re.match(r'^([A-Za-z0-9_\-\.]+)\s*=\s*["\'^~>=<]*([\d][^"\']*)', stripped)
            if m:
                name = m.group(1).lower().replace('_', '-')
                version = re.sub(r'[^0-9\.]', '', m.group(2).split(',')[0])
                if version:
                    deps[name] = version
    return deps


def _parse_package_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    deps = {}
    for section in ('dependencies', 'devDependencies'):
        for name, version in data.get(section, {}).items():
            if name.startswith('@types/'):
                continue
            m = re.search(r'(\d[\d\.]*)', str(version))
            if m:
                deps[name] = m.group(1)
    return deps


def _parse_composer_json(content: str) -> dict:
    SKIP = {'php', 'ext-json', 'ext-mbstring', 'ext-pdo', 'ext-openssl', 'ext-curl'}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    deps = {}
    for name, version in data.get('require', {}).items():
        if name in SKIP or name.startswith('ext-'):
            continue
        m = re.search(r'(\d[\d\.]*)', str(version))
        if m:
            deps[name] = m.group(1)
    return deps


# ---------------------------------------------------------------------------
# Registry lookups
# ---------------------------------------------------------------------------

def _get_latest_pypi(package: str, cache: dict) -> tuple:
    """Returns (version, is_deprecated, deprecated_reason)."""
    if package in cache:
        return cache[package]
    try:
        r = requests.get(
            f'https://pypi.org/pypi/{package}/json',
            timeout=8, headers={'User-Agent': 'MissionControl/1.0'},
        )
        if r.status_code == 200:
            info = r.json().get('info', {})
            version = info.get('version', '') or None
            classifiers = info.get('classifiers', [])
            yanked = info.get('yanked', False)
            is_deprecated = bool(yanked) or any(
                'Inactive' in c or 'Deprecated' in c or '7 - Inactive' in c
                for c in classifiers
            )
            reason = info.get('yanked_reason', '') or ''
            result = (version, is_deprecated, reason)
            cache[package] = result
            return result
    except Exception:
        pass
    result = (None, False, '')
    cache[package] = result
    return result


def _get_latest_npm(package: str, cache: dict) -> tuple:
    """Returns (version, is_deprecated, deprecated_reason)."""
    if package in cache:
        return cache[package]
    try:
        r = requests.get(
            f'https://registry.npmjs.org/{package}/latest',
            timeout=8, headers={'User-Agent': 'MissionControl/1.0'},
        )
        if r.status_code == 200:
            data = r.json()
            version = data.get('version', '') or None
            deprecated = data.get('deprecated', '')
            result = (version, bool(deprecated), str(deprecated) if deprecated else '')
            cache[package] = result
            return result
    except Exception:
        pass
    result = (None, False, '')
    cache[package] = result
    return result


def _get_latest_packagist(package: str, cache: dict) -> tuple:
    """Returns (version, is_deprecated, deprecated_reason)."""
    if package in cache:
        return cache[package]
    parts = package.split('/', 1)
    if len(parts) != 2:
        cache[package] = (None, False, '')
        return (None, False, '')
    try:
        r = requests.get(
            f'https://packagist.org/p2/{parts[0]}/{parts[1]}.json',
            timeout=8, headers={'User-Agent': 'MissionControl/1.0'},
        )
        if r.status_code == 200:
            versions = r.json().get('packages', {}).get(package, [])
            for v in versions:
                tag = v.get('version', '')
                if tag and not any(x in tag.lower() for x in ('dev', 'alpha', 'beta', 'rc')):
                    clean = tag.lstrip('v')
                    abandoned = v.get('abandoned', False)
                    reason = 'Package abandoned' if abandoned else ''
                    result = (clean, bool(abandoned), reason)
                    cache[package] = result
                    return result
    except Exception:
        pass
    result = (None, False, '')
    cache[package] = result
    return result


def _registry_url(ecosystem: str, package: str) -> str:
    if ecosystem == 'pypi':
        return f'https://pypi.org/project/{package}/'
    if ecosystem == 'npm':
        return f'https://www.npmjs.com/package/{package}'
    if ecosystem == 'packagist':
        return f'https://packagist.org/packages/{package}'
    return ''


# ---------------------------------------------------------------------------
# Main fetcher
# ---------------------------------------------------------------------------

def fetch_dependency_updates(
    repository: Repository,
    token=None,
    dry_run=False,
    registry_cache: dict = None,
) -> list:
    if registry_cache is None:
        registry_cache = {}

    parsed = _parse_owner_repo(repository.url)
    if not parsed:
        return []

    owner, repo_name = parsed
    hdrs = _github_headers(token)
    platform = repository.platform
    items = []

    for manifest_path, ecosystem in MANIFEST_FILES:
        try:
            result = _fetch_manifest_content(owner, repo_name, manifest_path, hdrs)
        except Exception:
            logger.exception('Failed fetching %s from %s', manifest_path, repository.name)
            continue

        if result is None:
            continue

        content, blob_sha = result

        snapshot, _ = DependencySnapshot.objects.get_or_create(
            repository=repository,
            manifest_path=manifest_path,
            defaults={'ecosystem': ecosystem, 'manifest_sha': '', 'dependencies': []},
        )

        # Parse if new or changed
        if snapshot.manifest_sha == blob_sha and snapshot.dependencies:
            pinned = {d['name']: d['pinned_version'] for d in snapshot.dependencies}
        else:
            pinned = _parse_manifest(manifest_path, content)

        if not pinned:
            continue

        ns = registry_cache.setdefault(ecosystem, {})
        dep_records = []
        new_items = []

        for pkg_name, pinned_version in pinned.items():
            if ecosystem == 'pypi':
                latest, is_deprecated, deprecated_reason = _get_latest_pypi(pkg_name, ns)
            elif ecosystem == 'npm':
                latest, is_deprecated, deprecated_reason = _get_latest_npm(pkg_name, ns)
            elif ecosystem == 'packagist':
                latest, is_deprecated, deprecated_reason = _get_latest_packagist(pkg_name, ns)
            else:
                latest, is_deprecated, deprecated_reason = None, False, ''

            pinned_major = _parse_major(pinned_version)
            latest_major = _parse_major(latest) if latest else None
            is_major_outdated = (
                pinned_major is not None
                and latest_major is not None
                and latest_major > pinned_major
            )

            dep_records.append({
                'name': pkg_name,
                'pinned_version': pinned_version,
                'latest_version': latest or '',
                'latest_major': latest_major,
                'is_major_outdated': is_major_outdated,
                'is_deprecated': is_deprecated,
                'deprecated_reason': deprecated_reason,
            })

            if is_deprecated:
                dep_ref = f'{pkg_name}:deprecated'
                if not NewsItem.objects.filter(
                    platform=platform,
                    source_type=NewsItemSourceType.DEPENDENCY_OUTDATED,
                    source_ref=dep_ref,
                ).exists():
                    new_items.append({
                        'platform': platform,
                        'source_type': NewsItemSourceType.DEPENDENCY_OUTDATED,
                        'title': f'{pkg_name}: package deprecated ({manifest_path})',
                        'body': deprecated_reason or 'This package has been marked as deprecated or abandoned.',
                        'url': _registry_url(ecosystem, pkg_name),
                        'published_at': datetime.now(tz=timezone.utc),
                        'source_ref': dep_ref,
                    })
            elif is_major_outdated:
                source_ref = f'{pkg_name}:v{latest_major}'
                if not NewsItem.objects.filter(
                    platform=platform,
                    source_type=NewsItemSourceType.DEPENDENCY_OUTDATED,
                    source_ref=source_ref,
                ).exists():
                    new_items.append({
                        'platform': platform,
                        'source_type': NewsItemSourceType.DEPENDENCY_OUTDATED,
                        'title': (
                            f'{pkg_name}: v{pinned_major} → v{latest_major} available'
                            f' ({manifest_path})'
                        ),
                        'body': (
                            f'Current pinned: {pinned_version}. Latest: {latest}. '
                            f'Repository: {repository.name}.'
                        ),
                        'url': _registry_url(ecosystem, pkg_name),
                        'published_at': datetime.now(tz=timezone.utc),
                        'source_ref': source_ref,
                    })

        if not dry_run:
            snapshot.manifest_sha = blob_sha
            snapshot.ecosystem = ecosystem
            snapshot.dependencies = dep_records
            snapshot.scanned_at = datetime.now(tz=timezone.utc)
            snapshot.save()

        items.extend(new_items)

    return items


def _fetch_manifest_content(
    owner: str, repo_name: str, path: str, hdrs: dict
) -> Optional[tuple]:
    r = requests.get(
        f'{GITHUB_API}/repos/{owner}/{repo_name}/contents/{path}',
        headers=hdrs, timeout=10,
    )
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        logger.warning('Unexpected status %s fetching %s from %s/%s', r.status_code, path, owner, repo_name)
        return None
    data = r.json()
    blob_sha = data.get('sha', '')
    encoded = data.get('content', '')
    content = base64.b64decode(encoded).decode('utf-8', errors='replace')
    return content, blob_sha


def _parse_manifest(manifest_path: str, content: str) -> dict:
    if manifest_path == 'requirements.txt':
        return _parse_requirements_txt(content)
    if manifest_path == 'pyproject.toml':
        return _parse_pyproject_toml(content)
    if manifest_path == 'package.json':
        return _parse_package_json(content)
    if manifest_path == 'composer.json':
        return _parse_composer_json(content)
    return {}

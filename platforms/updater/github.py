import logging
import re
from datetime import datetime, timezone

import requests

from platforms.models import (
    Deployment, NewsItem, NewsItemSourceType, Repository, RepositoryState,
)

logger = logging.getLogger(__name__)
GITHUB_API = 'https://api.github.com'


def _headers(token=None):
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


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return datetime.now(tz=timezone.utc)


def _exists(platform, source_type: str, source_ref: str) -> bool:
    return NewsItem.objects.filter(
        platform=platform, source_type=source_type, source_ref=source_ref,
    ).exists()


def fetch_github_activity(repository: Repository, token=None, dry_run=False) -> list:
    parsed = _parse_owner_repo(repository.url)
    if not parsed:
        logger.warning('Cannot parse GitHub URL for %s: %s', repository.name, repository.url)
        return []

    owner, repo_name = parsed
    hdrs = _headers(token)
    platform = repository.platform
    items = []

    state, _ = RepositoryState.objects.get_or_create(repository=repository)

    # Sync last_deployed_sha from the platform's latest deployment
    latest_deploy = (
        Deployment.objects
        .filter(platform=platform)
        .order_by('-deployed_at')
        .first()
    )
    if latest_deploy and latest_deploy.version:
        state.last_deployed_sha = latest_deploy.version[:40]

    # --- HEAD SHA ---
    head_sha = ''
    try:
        r = requests.get(
            f'{GITHUB_API}/repos/{owner}/{repo_name}/branches/{repository.default_branch}',
            headers=hdrs, timeout=10,
        )
        if r.status_code == 200:
            head_sha = r.json().get('commit', {}).get('sha', '')
        elif r.status_code == 404:
            logger.warning(
                'Branch %s not found for %s/%s', repository.default_branch, owner, repo_name
            )
    except Exception:
        logger.exception('Failed fetching branch for %s', repository.name)

    # --- Deployment lag ---
    if (head_sha
            and state.last_deployed_sha
            and head_sha != state.last_deployed_sha
            and not head_sha.startswith(state.last_deployed_sha[:7])):
        source_ref = f'lag:{head_sha[:12]}'
        if not _exists(platform, NewsItemSourceType.DEPLOYMENT_LAG, source_ref):
            compare_url = (
                f'https://github.com/{owner}/{repo_name}'
                f'/compare/{state.last_deployed_sha[:12]}...{head_sha[:12]}'
            )
            items.append({
                'platform': platform,
                'source_type': NewsItemSourceType.DEPLOYMENT_LAG,
                'title': f'{repository.name}: undeployed commits on {repository.default_branch}',
                'body': (
                    f'HEAD is now {head_sha[:12]}. '
                    f'Last recorded deployment: {state.last_deployed_sha[:12]}.'
                ),
                'url': compare_url,
                'published_at': datetime.now(tz=timezone.utc),
                'source_ref': source_ref,
            })

    # --- Commits since last check ---
    try:
        r = requests.get(
            f'{GITHUB_API}/repos/{owner}/{repo_name}/commits',
            headers=hdrs,
            params={'sha': repository.default_branch, 'per_page': 30},
            timeout=10,
        )
        if r.status_code == 200:
            all_commits = r.json()
            if state.last_checked_sha:
                new_commits = []
                for c in all_commits:
                    if c.get('sha', '')[:40] == state.last_checked_sha:
                        break
                    new_commits.append(c)
            else:
                new_commits = all_commits[:5]

            if new_commits:
                n = len(new_commits)
                latest = new_commits[0]
                latest_sha = (latest.get('sha') or '')[:40]
                msg = (
                    (latest.get('commit', {}).get('message') or '')
                    .splitlines()[0][:120]
                )
                pub = _parse_dt(
                    (latest.get('commit', {}).get('committer', {}).get('date') or '')
                )
                source_ref = latest_sha[:12]
                if source_ref and not _exists(platform, NewsItemSourceType.GITHUB_COMMIT, source_ref):
                    s = 's' if n > 1 else ''
                    items.append({
                        'platform': platform,
                        'source_type': NewsItemSourceType.GITHUB_COMMIT,
                        'title': (
                            f'{n} new commit{s} on {repository.default_branch} · {repository.name}'
                        ),
                        'body': f'Latest: {msg}' if msg else '',
                        'url': (
                            f'https://github.com/{owner}/{repo_name}'
                            f'/commits/{repository.default_branch}'
                        ),
                        'published_at': pub,
                        'source_ref': source_ref,
                    })
    except Exception:
        logger.exception('Failed fetching commits for %s', repository.name)

    # --- Latest release ---
    try:
        r = requests.get(
            f'{GITHUB_API}/repos/{owner}/{repo_name}/releases/latest',
            headers=hdrs, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            tag = data.get('tag_name', '')
            if tag and not _exists(platform, NewsItemSourceType.GITHUB_RELEASE, tag):
                items.append({
                    'platform': platform,
                    'source_type': NewsItemSourceType.GITHUB_RELEASE,
                    'title': f'{repository.name} — {data.get("name") or tag}',
                    'body': (data.get('body') or '')[:500],
                    'url': data.get('html_url', ''),
                    'published_at': _parse_dt(data.get('published_at') or ''),
                    'source_ref': tag,
                })
    except Exception:
        logger.exception('Failed fetching releases for %s', repository.name)

    # Persist updated state
    if not dry_run:
        if head_sha:
            state.last_checked_sha = head_sha
        state.last_checked_at = datetime.now(tz=timezone.utc)
        state.save()

    return items

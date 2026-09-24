import logging

from platforms.models import HealthStatus, NewsItem, NewsItemSourceType, Platform

logger = logging.getLogger(__name__)


def fetch_health_events(platform: Platform, dry_run=False) -> list:
    checks = list(
        platform.health_checks.order_by('-checked_at')[:2]
    )
    if len(checks) < 2:
        return []

    latest, previous = checks[0], checks[1]
    if latest.status == previous.status:
        return []

    source_ref = str(latest.pk)
    if NewsItem.objects.filter(
        platform=platform,
        source_type=NewsItemSourceType.HEALTH_EVENT,
        source_ref=source_ref,
    ).exists():
        return []

    prev_label = previous.get_status_display()
    curr_label = latest.get_status_display()

    if latest.status == HealthStatus.DOWN:
        title = f'{platform.name} is DOWN (was {prev_label})'
    elif latest.status == HealthStatus.HEALTHY and previous.status in (
        HealthStatus.DOWN, HealthStatus.DEGRADED
    ):
        title = f'{platform.name} health restored — now {curr_label}'
    elif latest.status == HealthStatus.DEGRADED:
        title = f'{platform.name} is DEGRADED (was {prev_label})'
    else:
        title = f'{platform.name}: health changed from {prev_label} to {curr_label}'

    return [{
        'platform': platform,
        'source_type': NewsItemSourceType.HEALTH_EVENT,
        'title': title,
        'body': latest.error_info or '',
        'url': '',
        'published_at': latest.checked_at,
        'source_ref': source_ref,
    }]

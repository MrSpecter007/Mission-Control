"""Health check service — isolated, testable, no UI dependencies."""
import re
import time
from datetime import datetime, timezone

import requests
from requests.exceptions import (
    ConnectionError, Timeout, SSLError, TooManyRedirects, MissingSchema,
    InvalidURL, RequestException,
)

from .models import HealthCheck, HealthStatus, Platform, Service, MonitoredURL


TIMEOUT_SECONDS = 10
_OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:(image|title|description)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_OG_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:(image|title|description)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)


def _extract_preview(html: str, base_url: str = '') -> dict:
    """Pull og:image, og:title, og:description (and fallback <title>) from HTML."""
    preview = {}
    for m in _OG_RE.finditer(html):
        preview[m.group(1)] = m.group(2).strip()
    for m in _OG_RE2.finditer(html):
        preview[m.group(2)] = m.group(1).strip()
    if 'title' not in preview:
        t = _TITLE_RE.search(html)
        if t:
            preview['title'] = re.sub(r'<[^>]+>', '', t.group(1)).strip()
    # Make og:image absolute if it's a relative URL
    img = preview.get('image', '')
    if img and base_url and not img.startswith(('http://', 'https://', '//')):
        from urllib.parse import urljoin
        preview['image'] = urljoin(base_url, img)
    elif img and img.startswith('//'):
        preview['image'] = 'https:' + img
    return preview


def run_health_check(platform: Platform, service: Service | None = None) -> HealthCheck:
    """
    Run an HTTP health check against the platform's primary domain and all
    monitored URLs. Always returns a HealthCheck record; never raises.
    """
    endpoint = _resolve_endpoint(platform)

    if not endpoint:
        return HealthCheck.objects.create(
            platform=platform,
            service=service,
            endpoint='',
            status=HealthStatus.UNKNOWN,
            checked_at=datetime.now(tz=timezone.utc),
            error_info='No endpoint available — no domain configured',
        )

    return _perform_check(platform, service, endpoint)


def _resolve_endpoint(platform: Platform) -> str:
    domain = platform.primary_domain
    if domain:
        return domain.url
    domain = platform.domains.filter(status='active').first()
    if domain:
        return domain.url
    return ''


def _probe(url: str, capture_body: bool = False) -> dict:
    """Check a single URL, return a result dict. Never raises."""
    result = {'url': url, 'status': HealthStatus.UNKNOWN, 'http_status': None, 'response_time_ms': None, 'error': '', '_body': ''}
    try:
        start = time.monotonic()
        r = requests.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True, headers={'User-Agent': 'MissionControl/1.0 healthcheck'})
        result['response_time_ms'] = round((time.monotonic() - start) * 1000, 2)
        result['http_status'] = r.status_code
        if r.status_code < 400:
            result['status'] = HealthStatus.HEALTHY
        elif r.status_code < 500:
            result['status'] = HealthStatus.DEGRADED
            result['error'] = f'HTTP {r.status_code}'
        else:
            result['status'] = HealthStatus.DOWN
            result['error'] = f'HTTP {r.status_code}'
        if capture_body and 'text/html' in r.headers.get('content-type', ''):
            result['_body'] = r.text[:32_000]
    except Timeout:
        result['status'] = HealthStatus.DOWN
        result['error'] = f'Timed out after {TIMEOUT_SECONDS}s'
    except SSLError as exc:
        result['status'] = HealthStatus.DOWN
        result['error'] = f'SSL error: {exc}'
    except ConnectionError as exc:
        result['status'] = HealthStatus.DOWN
        result['error'] = f'Connection error: {exc}'
    except TooManyRedirects:
        result['status'] = HealthStatus.DEGRADED
        result['error'] = 'Too many redirects'
    except (MissingSchema, InvalidURL) as exc:
        result['status'] = HealthStatus.UNKNOWN
        result['error'] = f'Invalid URL: {exc}'
    except RequestException as exc:
        result['status'] = HealthStatus.DOWN
        result['error'] = f'Request failed: {exc}'
    except Exception as exc:  # noqa: BLE001
        result['status'] = HealthStatus.UNKNOWN
        result['error'] = f'Unexpected error: {exc}'
    return result


def _perform_check(platform: Platform, service: Service | None, endpoint: str) -> HealthCheck:
    checked_at = datetime.now(tz=timezone.utc)

    # Primary domain check — capture body to extract og preview
    primary = _probe(endpoint, capture_body=True)
    status = primary['status']
    error_info = primary['error']
    homepage_preview = _extract_preview(primary['_body'], base_url=endpoint) if primary['_body'] else {}

    # Monitored URLs
    url_results = []
    base = endpoint.rstrip('/')
    for mu in platform.monitored_urls.all():
        path = '/' + mu.path.lstrip('/')
        result = _probe(base + path)
        url_results.append({
            'label': mu.label,
            'path': mu.path,
            'url': base + path,
            'is_critical': mu.is_critical,
            'status': result['status'],
            'http_status': result['http_status'],
            'response_time_ms': result['response_time_ms'],
            'error': result['error'],
        })
        # A critical URL that is DOWN or DEGRADED downgrades overall status
        if mu.is_critical and result['status'] == HealthStatus.DOWN:
            status = HealthStatus.DOWN
            if not error_info:
                error_info = f'{mu.label} is down'
        elif mu.is_critical and result['status'] == HealthStatus.DEGRADED and status == HealthStatus.HEALTHY:
            status = HealthStatus.DEGRADED
            if not error_info:
                error_info = f'{mu.label} is degraded'

    return HealthCheck.objects.create(
        platform=platform,
        service=service,
        endpoint=endpoint,
        status=status,
        http_status=primary['http_status'],
        response_time_ms=primary['response_time_ms'],
        checked_at=checked_at,
        error_info=error_info,
        url_results=url_results,
        homepage_preview=homepage_preview,
    )


def get_default_service_name(framework: str) -> tuple[str, str]:
    """Return (service_name, service_type) based on framework."""
    from .models import ServiceType
    mapping = {
        'wagtail': ('Wagtail Application', ServiceType.WEB),
        'django': ('Django Application', ServiceType.WEB),
        'oscar': ('Oscar Commerce', ServiceType.WEB),
        'wordpress': ('WordPress Application', ServiceType.WEB),
        'laravel': ('Laravel Application', ServiceType.WEB),
        'custom': ('Web Application', ServiceType.WEB),
        'other': ('Web Application', ServiceType.WEB),
    }
    return mapping.get(framework, ('Web Application', ServiceType.WEB))

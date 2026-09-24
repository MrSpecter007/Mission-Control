from datetime import timedelta
from django.utils import timezone


def updates_context(request):
    if not request.user.is_authenticated:
        return {}
    from platforms.models import NewsItem
    since = timezone.now() - timedelta(hours=24)
    count = NewsItem.objects.filter(fetched_at__gte=since).count()
    return {'updates_unread_count': count}

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from .models import ActivityEntry


class MilestoneFeed(Feed):
    title = 'Mission Control — Milestones'
    link = '/activity/'
    description = 'Significant milestones and achievements across the estate.'
    feed_type = Atom1Feed

    def items(self):
        return (
            ActivityEntry.objects
            .filter(is_milestone=True)
            .select_related('platform')
            .order_by('-occurred_at')[:50]
        )

    def item_title(self, item):
        if item.platform:
            return f'{item.platform.name} — {item.title}'
        return item.title

    def item_description(self, item):
        parts = []
        if item.get_activity_type_display():
            parts.append(f'Type: {item.get_activity_type_display()}')
        if item.description:
            parts.append(item.description)
        return '\n\n'.join(parts)

    def item_pubdate(self, item):
        return item.occurred_at

    def item_link(self, item):
        if item.ref_url:
            return item.ref_url
        if item.platform:
            return item.platform.get_absolute_url()
        return '/activity/'

    def item_guid(self, item):
        return f'mission-control-activity-{item.pk}'

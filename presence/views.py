import datetime

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import PresenceEvent

# Events older than this are purged on each poll request
_EVENT_TTL = datetime.timedelta(minutes=5)

# Maximum look-back window: clients cannot request events older than this,
# which prevents accidental full-table scans and ensures newly connected
# visitors never receive stale notifications.
_MAX_LOOKBACK = datetime.timedelta(seconds=30)


def presence_events(request):
    now = timezone.now()

    # Purge expired events to keep the table tiny
    PresenceEvent.objects.filter(created_at__lt=now - _EVENT_TTL).delete()

    # Resolve the 'since' boundary
    floor = now - _MAX_LOOKBACK
    since = floor

    since_str = request.GET.get("since", "")
    if since_str:
        parsed = parse_datetime(since_str)
        if parsed is not None:
            # Use the client timestamp if it's more recent than the floor,
            # so new page loads don't receive events from before they connected.
            if parsed > floor:
                since = parsed

    events = PresenceEvent.objects.filter(created_at__gt=since).order_by("created_at")

    return JsonResponse(
        {
            "events": [
                {
                    "id": e.id,
                    "type": e.event_type,
                    "message": e.message,
                    "ts": e.created_at.isoformat(),
                }
                for e in events
            ]
        }
    )

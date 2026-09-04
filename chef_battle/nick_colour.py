"""What colour a person's name is in the hall.

The Owner, 2026-09-04:

    A viewer with no tokens has a grey name. One who has bought up to 100 goes
    light blue, 100 to 500 blue, 500 and above purple. A viewer who joins a
    chef's fan club is green. Every admin on the site is red. It is cosmetic,
    it costs nothing, but it is still nice for the viewer.

    We count everything bought within one month. When the month runs out - no
    purchase in thirty days AND nothing on the account - the name goes grey
    again. If there are tokens on the account, the colour is held at whatever
    that balance is worth.

READ THAT LAST PART CAREFULLY, because it is the whole rule: a name is not
"what he spent" and not "what he holds", it is the BETTER of the two. Somebody
who bought six hundred tokens this week and spent every one of them on the
chefs keeps his purple - spending on the arena is the point, and a colour that
punished it would be telling people to sit on their tokens. Somebody who bought
nothing this month but is holding two hundred keeps his blue. Somebody with
neither goes grey.

DECIDED ON THE SERVER, ALWAYS. The tier is computed here and handed to the
renderer as a name; nothing downstream reads a colour out of a request, so a
browser that posts {"tier": "purple"} changes nothing at all. Same rule the
chat's admin role already follows.
"""
from __future__ import annotations

from django.db.models import Sum
from django.utils import timezone

#: How far back a purchase still counts towards a name's colour.
PURCHASE_WINDOW = timezone.timedelta(days=30)

#: Grey below the first entry; the tier is the last one whose floor is reached.
#: The Owner's bands: up to 100 light blue, 100-500 blue, 500 and above purple.
TIERS = (
    (500, "purple"),
    (100, "blue"),
    (1, "sky"),
)

GREY = "grey"
FAN = "fan"
ADMIN = "admin"

#: The Owner's own name, and the only one that is gold. He asked for it on
#: 2026-09-04: "цвет ника GreenBear - всегда золотой и переливается".
#:
#: ALWAYS means always: it is answered before the fan club and before any
#: purchase, and it outranks the admin red in the stylesheet too. He is the
#: site rather than a person speaking for it.
#:
#: This colours a NAME and touches nothing else. AGENTS.md 18 puts his account,
#: his presence on the site and his page beyond an agent's reach; a tier string
#: computed from settings.OWNER_SLUG writes no field, sets no flag and changes
#: no row.
OWNER = "owner"

#: Every value this module can return. The renderer's stylesheet is written
#: against exactly these and the test that pins them reads this tuple.
ALL_TIERS = (GREY, "sky", "blue", "purple", FAN, OWNER, ADMIN)


def _tier_for_amount(amount: int) -> str:
    for floor, name in TIERS:
        if amount >= floor:
            return name
    return GREY


def tiers_for(author_ids) -> dict[int, str]:
    """`{author_id: tier}` for these people, in three queries whatever the size.

    Batched for the same reason team_tags_for is: this runs on every chat poll,
    and a per-line lookup would be N+1 against the wallet and order tables at
    the busiest moment the arena has.
    """
    from django.conf import settings
    from recipes.models import RecipeAuthor

    from .models import ChefFanClub, TokenOrder, TokenWallet

    author_ids = {aid for aid in author_ids if aid}
    if not author_ids:
        return {}

    # 0. The Owner, answered before anything else is even counted.
    owner_ids = set(
        RecipeAuthor.objects
        .filter(pk__in=author_ids, slug=settings.OWNER_SLUG)
        .values_list("pk", flat=True)
    )

    # 1. What they are holding now.
    balances = dict(
        TokenWallet.objects.filter(chef_id__in=author_ids)
        .values_list("chef_id", "balance")
    )

    # 2. What they bought inside the window. Only orders that were actually
    #    paid for: a checkout session somebody abandoned is not a purchase, and
    #    clawed-back tokens are removed because a refunded order is not one
    #    either.
    since = timezone.now() - PURCHASE_WINDOW
    recent = {}
    rows = (
        TokenOrder.objects
        .filter(wallet__chef_id__in=author_ids, credited_at__isnull=False,
                credited_at__gte=since)
        .values("wallet__chef_id")
        .annotate(bought=Sum("tokens"), clawed=Sum("clawed_tokens"))
    )
    for row in rows:
        net = (row["bought"] or 0) - (row["clawed"] or 0)
        recent[row["wallet__chef_id"]] = max(0, net)

    # 3. Who stands with a chef. Green is not bought, so it is not a number and
    #    it does not compete with one - it simply wins.
    fans = set(
        ChefFanClub.objects
        .filter(viewer_id__in=author_ids, left_at__isnull=True)
        .values_list("viewer_id", flat=True)
    )

    out = {}
    for author_id in author_ids:
        if author_id in owner_ids:
            out[author_id] = OWNER
            continue
        if author_id in fans:
            out[author_id] = FAN
            continue
        out[author_id] = _tier_for_amount(
            max(balances.get(author_id, 0), recent.get(author_id, 0))
        )
    return out


def tier_for(author) -> str:
    """One person's tier. Prefer tiers_for() wherever there is more than one."""
    if author is None or getattr(author, "pk", None) is None:
        return GREY
    return tiers_for({author.pk}).get(author.pk, GREY)


def fan_club_of(viewer, chef):
    """The live membership row, or None."""
    from .models import ChefFanClub

    if viewer is None or chef is None:
        return None
    return ChefFanClub.objects.filter(
        viewer=viewer, chef=chef, left_at__isnull=True).first()


def join_fan_club(*, viewer, chef):
    """Stand with a chef. Idempotent: joining twice returns the same row."""
    from .models import ChefFanClub

    if viewer is None or chef is None:
        raise ValueError("A fan club needs both a viewer and a chef.")
    if viewer.pk == chef.pk:
        raise ValueError("A chef cannot join his own fan club.")
    existing = fan_club_of(viewer, chef)
    if existing is not None:
        return existing
    return ChefFanClub.objects.create(viewer=viewer, chef=chef)


def leave_fan_club(*, viewer, chef):
    """Step away. The row stays and is stamped, so the history survives."""
    membership = fan_club_of(viewer, chef)
    if membership is None:
        return None
    membership.left_at = timezone.now()
    membership.save(update_fields=["left_at"])
    return membership


def fan_count(chef) -> int:
    from .models import ChefFanClub

    return ChefFanClub.objects.filter(chef=chef, left_at__isnull=True).count()

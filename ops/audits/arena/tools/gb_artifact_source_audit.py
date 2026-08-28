"""Read-only: who owns the ChefArtifact rows marked `purchased`, and when.

`ChefArtifact.source` defaults to `purchased`, and the 2026-07-15 catalogue
seed never set it, so rows that were GRANTED FOR TESTING claim to have been
bought. Before anything is deleted, this prints what is actually in there:
the dates, the owners, and whether any row is backed by a real token
transaction - a row that cost somebody tokens is not test data and must not
be swept up with it.

Writes nothing. Run it on production as the `deploy` user:

    cd /srv/culineire/current && DJANGO_ENV_FILE=/srv/culineire/shared/.env \
        /srv/culineire/venv/bin/python ops/audits/arena/tools/gb_artifact_source_audit.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db.models import Count  # noqa: E402

from chef_battle.models import ChefArtifact  # noqa: E402

qs = ChefArtifact.objects.filter(source="purchased")
print("rows marked purchased:", qs.count())
print("distinct chefs:", qs.values("chef").distinct().count())

dates = qs.values_list("earned_at", flat=True).order_by("earned_at")
if dates:
    print("earliest:", dates.first())
    print("latest:  ", dates.last())

print("\nby calendar day:")
seen = {}
for stamp in qs.values_list("earned_at", flat=True):
    key = stamp.date().isoformat()
    seen[key] = seen.get(key, 0) + 1
for day in sorted(seen):
    print("  %s  %4d" % (day, seen[day]))

fields = {f.name for f in ChefArtifact._meta.get_fields()}
if "token_transaction" in fields:
    paid = qs.exclude(token_transaction=None)
    print("\nbacked by a token transaction (NOT test data):", paid.count())
    for row in paid.values("chef__name", "artifact__name")[:20]:
        print("   ", row)
else:
    print("\nno token_transaction field on ChefArtifact")

print("\ntop owners:")
for row in (qs.values("chef__name", "chef__user__username")
              .annotate(n=Count("id")).order_by("-n")[:15]):
    print("   ", row)

print("\nthe Owner's own accounts:")
for name in ("greenbear", "CrestedTen", "Jam-Oliver"):
    print("   %-12s %d" % (
        name, qs.filter(chef__user__username__iexact=name).count()))

print("\nfor comparison, rows NOT marked purchased:")
for row in (ChefArtifact.objects.exclude(source="purchased")
              .values("source").annotate(n=Count("id")).order_by("-n")):
    print("   ", row)

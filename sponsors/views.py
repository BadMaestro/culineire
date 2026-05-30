import json

from django.shortcuts import render

from .models import SponsorCell


def puzzle_page(request):
    cells = SponsorCell.objects.all().order_by("ring", "position_in_ring")

    cells_json = json.dumps([c.as_dict() for c in cells])

    sold = cells.filter(status=SponsorCell.Status.SOLD).count()
    reserved = cells.filter(status=SponsorCell.Status.RESERVED).count()
    available = cells.filter(status=SponsorCell.Status.AVAILABLE).count()
    # exclude centre from totals shown to visitors
    sellable_total = cells.exclude(ring=0).count()

    return render(
        request,
        "sponsors/puzzle.html",
        {
            "cells_json": cells_json,
            "sold": sold,
            "reserved": reserved,
            "available": available,
            "sellable_total": sellable_total,
            "percent_sold": round((sold / sellable_total * 100) if sellable_total else 0),
        },
    )

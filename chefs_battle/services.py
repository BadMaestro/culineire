from __future__ import annotations

from typing import Any

from django.utils import timezone

from chefs_battle.models import ChefsBattleRoadmapItem

# Each entry: (title, phase, is_done, is_blocker)
ROADMAP_MILESTONES: list[tuple[str, str, bool, bool]] = [
    # Phase 1 — Concept
    ("Define Chefs Battle concept and rules",   "Phase 1: Concept",  False, False),
    ("Define target audience and platform",     "Phase 1: Concept",  False, False),
    ("Define judging criteria",                 "Phase 1: Concept",  False, False),
    # Phase 2 — Design
    ("Design data model",                       "Phase 2: Design",   False, False),
    ("Design participant flow",                 "Phase 2: Design",   False, False),
    ("Design judging flow",                     "Phase 2: Design",   False, False),
    # Phase 3 — Build
    ("Build app skeleton",                      "Phase 3: Build",    True,  False),
    ("Build roadmap page",                      "Phase 3: Build",    True,  False),
]


def seed_roadmap_items() -> None:
    now = timezone.now()
    for index, (title, phase, is_done, is_blocker) in enumerate(ROADMAP_MILESTONES, start=1):
        ChefsBattleRoadmapItem.objects.update_or_create(
            title=title,
            defaults={
                "phase": phase,
                "sort_order": index,
                "status": ChefsBattleRoadmapItem.Status.DONE if is_done else ChefsBattleRoadmapItem.Status.NOT_STARTED,
                "priority": ChefsBattleRoadmapItem.Priority.HIGH,
                "is_blocker": is_blocker,
                "completed_at": now if is_done else None,
            },
        )


def build_roadmap_context() -> dict[str, Any]:
    seed_roadmap_items()
    items = list(ChefsBattleRoadmapItem.objects.all())
    done_statuses = {ChefsBattleRoadmapItem.Status.DONE, ChefsBattleRoadmapItem.Status.SKIPPED}
    done_count = sum(1 for item in items if item.status in done_statuses)
    total_count = len(items)
    blockers = [item for item in items if item.is_blocker or item.status == ChefsBattleRoadmapItem.Status.BLOCKED]
    pending_items = [item for item in items if item.status not in done_statuses]
    completed_items = [item for item in items if item.status in done_statuses]
    return {
        "items": items,
        "completed_items": completed_items,
        "pending_items": pending_items,
        "blockers": blockers,
        "done_count": done_count,
        "total_count": total_count,
        "percent": round((done_count / total_count) * 100) if total_count else 0,
        "current_phase": "Concept and planning",
        "last_updated": max((item.updated_at for item in items), default=timezone.now()),
    }

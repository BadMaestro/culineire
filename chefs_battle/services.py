from __future__ import annotations

from typing import Any

from django.utils import timezone

from chefs_battle.models import ChefsBattleRoadmapItem

# Each entry: (title, phase, is_done, is_blocker)
ROADMAP_MILESTONES: list[tuple[str, str, bool, bool]] = [
    # Phase 0 — Architecture & Foundation
    ("Load ТЗ / Roadmap / Artifact documents into Claude",          "Phase 0: Architecture",  True,  False),
    ("Confirm app name: chef_battle (internal), Chef's Battle (public)", "Phase 0: Architecture", True, False),
    ("Create chef_battle Django app skeleton",                       "Phase 0: Architecture",  True,  False),
    ("Implement ChefBattleProfile model",                            "Phase 0: Architecture",  True,  False),
    ("Implement BattleChallenge model",                              "Phase 0: Architecture",  True,  False),
    ("Implement Battle model",                                       "Phase 0: Architecture",  True,  False),
    ("Implement BattleEntry model",                                  "Phase 0: Architecture",  True,  False),
    ("Implement BattleVote model",                                   "Phase 0: Architecture",  True,  False),
    ("Implement BattleEvent model",                                  "Phase 0: Architecture",  True,  False),
    ("Add all missing model fields per ТЗ Artifact 3",               "Phase 0: Architecture",  True,  False),
    ("Add BattleMoveTransaction / Artifact / Season skeleton models","Phase 0: Architecture",  True,  False),
    ("Service layer: challenge_service / battle_service",            "Phase 0: Architecture",  True,  False),
    ("Service layer: vote_service / rating_service / event_service", "Phase 0: Architecture",  True,  False),
    ("Register all models in Django Admin",                          "Phase 0: Architecture",  False, False),
    ("Admin actions: cancel / dispute / force-reveal / force-complete", "Phase 0: Architecture", False, False),
    ("Create selectors.py for read queries",                        "Phase 0: Architecture",  False, False),
    ("Split services.py into separate modules",                     "Phase 0: Architecture",  False, False),
    # Phase 1 — MVP Battle Core
    ("Challenge creation form and view",                             "Phase 1: MVP Core",      True,  False),
    ("Challenge accept / refuse / expire views",                     "Phase 1: MVP Core",      True,  False),
    ("Battle room public page",                                      "Phase 1: MVP Core",      True,  False),
    ("Submission deadline timer display",                            "Phase 1: MVP Core",      True,  False),
    ("Battle entry submission form",                                 "Phase 1: MVP Core",      True,  False),
    ("Hidden entries until reveal logic",                            "Phase 1: MVP Core",      True,  False),
    ("Public voting panel",                                          "Phase 1: MVP Core",      True,  False),
    ("Vote anti-abuse: duplicate / self-vote / window checks",       "Phase 1: MVP Core",      True,  False),
    ("Result calculation by public vote",                            "Phase 1: MVP Core",      True,  False),
    ("No-show / late submission handling",                           "Phase 1: MVP Core",      False, False),
    ("Rating and rank update on battle result",                      "Phase 1: MVP Core",      True,  False),
    ("Crown holder 24h system",                                      "Phase 1: MVP Core",      True,  False),
    ("Battle landing page (/battle/)",                               "Phase 1: MVP Core",      True,  False),
    ("Leaderboard page (/battle/leaderboard/)",                      "Phase 1: MVP Core",      True,  False),
    ("Homepage battle news integration",                             "Phase 1: MVP Core",      True,  False),
    ("Chef profile battle stats block",                              "Phase 1: MVP Core",      True,  False),
    ("Management command: auto-expire stale challenges",             "Phase 1: MVP Core",      False, False),
    # Phase 1 — Tests & Quality Gate
    ("Model and service tests: challenge lifecycle",                 "Phase 1: Tests",         True,  False),
    ("Model and service tests: voting and result",                   "Phase 1: Tests",         True,  False),
    ("Permission tests: anon / non-participant / hidden entries",    "Phase 1: Tests",         False, True),
    ("Anti-abuse tests: duplicate vote / self-vote / farm pair",     "Phase 1: Tests",         False, True),
    ("Regression: full test suite passes (python manage.py test)",   "Phase 1: Tests",         False, True),
    # Phase 2 — Social Visibility
    ("Activity feed integration across site",                        "Phase 2: Social",        False, False),
    ("Battle history archive page",                                  "Phase 2: Social",        False, False),
    ("Live pop-up notifications (SSE or polling)",                   "Phase 2: Social",        False, False),
    ("Crown and rank promotion announcements",                       "Phase 2: Social",        False, False),
    # Phase 3 — Energy Economy
    ("Battle moves earned from approved recipes / articles",         "Phase 3: Energy",        False, False),
    ("Move transaction ledger",                                      "Phase 3: Energy",        False, False),
    ("Daily / weekly caps and anti-farming rules",                   "Phase 3: Energy",        False, False),
    # Phase 4 — Combat Engine
    ("Attack / defence / block mechanics",                           "Phase 4: Combat",        False, False),
    ("Tactical round log",                                           "Phase 4: Combat",        False, False),
    # Phase 5 — Artifacts & Cosmetics
    ("Artifact inventory and equip system",                          "Phase 5: Artifacts",     False, False),
    ("Premium cosmetics (earn-only artifacts, optional paid cosmetics)", "Phase 5: Artifacts", False, False),
    # Phase 6 — Seasons & Clans
    ("Seasonal rankings and Hall of Fame",                           "Phase 6: Seasons",       False, False),
    ("Kitchen / clan system",                                        "Phase 6: Seasons",       False, False),
    # Phase 7 — Sponsorship & Media
    ("Sponsored battles and branded events",                         "Phase 7: Sponsorship",   False, False),
    ("Weekly battle recap and social snippet generation",            "Phase 7: Sponsorship",   False, False),
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
        "current_phase": "Phase 0 — Architecture complete. Phase 1 MVP Core in progress.",
        "last_updated": max((item.updated_at for item in items), default=timezone.now()),
    }

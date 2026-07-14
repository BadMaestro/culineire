from django.db import migrations


STAGES = [
    (1, "state_contract", "Battle state contract (all states)", "foundation"),
    (2, "realtime_transport", "Real-time transport (snapshot / reconnect / stale-event)", "foundation"),
    (3, "permissions", "Server-side permissions per action", "foundation"),
    (4, "page_shell", "Arena route & broadcast page shell + top nav", "frame"),
    (5, "matchup_header", "Matchup header (chef identity L/R, VS, theme strip)", "frame"),
    (6, "dual_live_stage", "Dual live stage (video panels, overlays, fallback)", "live"),
    (7, "countdown_timer", "Central countdown timer (server-authoritative)", "live"),
    (8, "live_chat", "Live chat console (tabs, composer, moderation states)", "live"),
    (9, "supporters_support", "Supporters & support/gift actions", "live"),
    (10, "reactions", "Reactions", "live"),
    (11, "viewer_count", "Viewer count / presence", "live"),
    (12, "moderation_integration", "Moderation console integration (incl. observer votes)", "crosscutting"),
    (13, "empty_degraded_states", "Empty / degraded states (no battle, transport down, no-permission viewer)", "crosscutting"),
    (14, "accessibility", "Accessibility (WCAG 2.2 AA)", "crosscutting"),
    (15, "cross_device_mobile", "Cross-device / mobile", "crosscutting"),
    (16, "qa_rollout", "QA, tests & rollout", "crosscutting"),
]


def seed(apps, schema_editor):
    LiveArenaStage = apps.get_model("chef_battle", "LiveArenaStage")
    for order, key, title, group in STAGES:
        LiveArenaStage.objects.update_or_create(
            key=key,
            defaults={"order": order, "title": title, "phase_group": group},
        )


def unseed(apps, schema_editor):
    LiveArenaStage = apps.get_model("chef_battle", "LiveArenaStage")
    LiveArenaStage.objects.filter(key__in=[k for _, k, _, _ in STAGES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("chef_battle", "0074_livearenastage"),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]

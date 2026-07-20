# BATTLE RULES — Participation & Scheduling

## Author note
Defined by project creator.

---

## Battle count & progression

| Outcome | Effect on battle count |
|---------|----------------------|
| Win | +1 `wins` (counts toward level) |
| Loss | +1 `losses` (display only, does not affect level) |
| Refuse a challenge (manual) | **−1 battle** (floor at 0) |
| Auto-refuse (48h timeout) | **−1 battle** (floor at 0) |
| Slot auto-expire (12h no response) | **−1 battle** (floor at 0) |

**Floor rule**: battle count can never go below 0. If a chef has 0 battles
and incurs a penalty, it stays at 0.

Only victories count toward level progression (10 wins = level up, not 10 participations).

---

## Slot system — 1 slot per chef

Each chef has **one battle slot**. Only one active battle at a time.

### Slot lifecycle

```
Challenge issued → occupies challenger's slot
  ├─ Accepted within 12h → 24h timer starts for both chefs
  └─ Not accepted within 12h → slot freed; −1 battle to non-responder (floor 0)

Battle completes → slot freed; chef can accept or issue a new challenge
```

### Key rules

- **Acceptance window**: 12 hours from challenge issue
- **Battle window**: 24 hours from acceptance — both chefs complete
  combat + cooking + submission within this window
- **Occupied slot**: a chef with an active battle cannot accept or issue
  new challenges until the slot is free
- Manual refuse → −1 battle (floor 0)
- Slot auto-expires (12h no response) → −1 battle (floor 0)

### "Ready" button — scheduling combat within the 24h window

1. Chef A presses **"Ready"** — signals preparation is complete
2. Chef B sees the signal, presses **"Ready"**, and proposes a specific
   combat time within the remaining 24h window
3. Chef A confirms the proposed time → combat begins at that time

---

## Summary of automated actions

| Trigger | Action |
|---------|--------|
| Challenge not accepted in 12h | Slot freed; **−1 battle** to non-responder (floor 0) |
| Manual refuse | −1 battle to refuser; slot freed |
| 24h window expires without completion | Auto-cancel; non-compliant party −1 battle |
| Win recorded | +1 battle count; recalculate level |

---

## Implementation notes

### ChefBattleProfile fields
- `battles_completed` IntegerField default=0 (wins only)

### Battle model fields
- `accepted_at` DateTimeField null=True
- `battle_deadline` DateTimeField null=True — `accepted_at + 24h`
- `challenger_ready` BooleanField default=False
- `opponent_ready` BooleanField default=False
- `proposed_combat_time` DateTimeField null=True
- `combat_time_confirmed` BooleanField default=False

### Slot occupied check
```python
def has_active_battle(profile):
    active_statuses = [
        "accepted", "menu_locked", "active",
        "cooking", "presentation", "voting", "ingredient_penalty"
    ]
    return Battle.objects.filter(
        models.Q(challenger=profile) | models.Q(opponent=profile),
        status__in=active_statuses
    ).exists()
```

### Auto-tasks (cron / celery beat — run every 30 min)
- Find `declared` battles where `created_at < now() - 12h` → expire; −1 to non-responder
- Find active battles where `battle_deadline < now()` → auto-cancel; −1 to non-compliant party

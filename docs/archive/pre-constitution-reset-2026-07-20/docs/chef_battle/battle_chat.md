# BATTLE CHAT — Live Audience Comments

## Author note
Defined by project creator.

---

## Concept

Each battle page has a dedicated live chat window where authenticated users
can leave comments while the battle is in progress. Chat is visible to all
visitors but only logged-in users can post.

---

## UI placement

- Separate panel on the battle detail page, below or alongside the combat log
- Distinct from the Battle Log (which shows automated system events)
- Scrollable chat window with input field at the bottom
- Shows: username, timestamp, message
- Auto-scrolls to latest message

---

## Rules

- Only authenticated users can post
- Max message length: 280 characters
- No editing or deleting own messages (append-only log)
- Moderation: staff can delete individual messages
- Chat is open while battle status is in:
  `active`, `cooking`, `presentation`, `voting`
- Chat is read-only (archived) once battle is `completed` or `cancelled`

---

## Implementation notes

### Model: `BattleComment`
```python
class BattleComment(models.Model):
    battle = models.ForeignKey(Battle, on_delete=models.CASCADE,
                               related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.CharField(max_length=280)
    created_at = models.AutoDateTimeField()
    is_deleted = models.BooleanField(default=False)
```

### Endpoints
- `POST /chefs-battle/<pk>/comment/` — submit comment (login required)
- Comments loaded via AJAX or page refresh (polling every 15s while battle active)
- Staff delete: `POST /chefs-battle/comment/<id>/delete/`

### Template
- Separate `<section class="battle-chat">` panel on battle_detail.html
- Input form with CSRF, character counter (280 max)
- Read-only textarea replacement when battle is completed

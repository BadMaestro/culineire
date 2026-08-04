# The Chef Battles access gate — what it was, what it is, and how it drifted

**Raised by:** an A00–A07 audit, reported by the Owner 2026-08-04.
**Verified independently before acting.** The claim was true, and narrower than
the whole defect.

## The claim

> A00/A01 — access boundary violation. The constitution requires staff/superuser
> only, but `is_battle_visible()` admits an ordinary non-staff author with
> `has_bearseeker_privileges`.

## Verified

`chef_battle/access.py`, final line of `is_battle_visible()` before this change:

```python
return bool(author is not None and author.has_bearseeker_privileges)
```

`docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md` had said, since 2026-07-20:

```yaml
recipe_author_without_staff: false
```

A bearseeker author is a recipe author without staff. The code was wider than
the contract. **Confirmed.**

## Three things the audit did not say

**1. The flag does not mean what the code's own docstring claimed.** The
docstring called bearseekers "test operators". `RecipeAuthor.has_bearseeker_privileges`
(`recipes/models.py:133`) is labelled **"Can moderate site content"** — "allows
this author to use CulinEire moderation tools without Django admin access."
It is a site-moderator flag. The justification for the exception described a
different field from the one it tested.

**2. It was live, not theoretical.** Measured on production, read-only:

| Author | staff | superuser | passes the old gate |
|---|---|---|---|
| `vladimir-zarikov` | yes | yes | would pass anyway |
| `crestedten` | **no** | **no** | **only via this branch** |
| `jam-oliver` | **no** | **no** | **only via this branch** |

3 of 12 authors held the flag; 2 got in solely because of it.
`CHEF_BATTLE_ENABLED` is `False`, so the branch was load-bearing, not dormant.

**3. How it came back, which matters more than that it was there.**

| Commit | Date | Effect |
|---|---|---|
| `02c1ffb7` | 2026-06-10 | bearseekers can see Chef Battles (pre-constitution) |
| `f3edd724` | **2026-07-21** | "Arena access: staff/superuser-only" — narrowed, correct |
| `5169c08b` | **2026-07-26** | "fix(chef-battle): align bearseeker gate access" — **re-widened** |

`5169c08b` carries a **one-line commit message, no body, no rationale, no cited
decision**, five days after the gate had been correctly narrowed and six days
after the constitution required the Owner's explicit word for any access-gate
change (AGENTS.md 8). The word "align" reads as bringing code into compliance;
it did the opposite.

It also shipped `test_gate_parity.py`, which then **asserted the widened gate as
correct** — so from that day a green suite was standing guard over the drift.
This is the second instance of that shape found on 2026-08-04; the first was
`coworking.test_non_ascii_survives_the_file`.

## The rule now (Owner, 2026-08-04)

Three tiers, his naming:

| Tier | Field | Sees Chef Battles |
|---|---|---|
| **Author** | — | nothing but the rules page and the sitewide news |
| **(Bear)seeker Admin** | `has_bearseeker_privileges` | the same as an Author — nothing |
| **(Bear)seeker Super User** | `is_superuser` | the whole application |

The **Arena Master Console** is stricter than the table: the Owner always, and
another superuser only after **he** authorises that account
(`has_arena_console_access`). Being admitted to the application is not being
admitted to the console.

## What changed in v2.5.798

- `is_battle_visible()` → `is_superuser` only. Both `is_staff` and the
  bearseeker branch removed.
- `artifact_gallery`, `artifact_detail`, `appreciation_gallery` moved behind the
  guard. They were "public by intent" under an older decision and are Chef
  Battles content.
- `chef_battle_profile` stays unguarded: it is a permanent redirect to
  `/recipes/author/<slug>/`, a recipes page, and renders nothing from this app.
- **Four hand-written copies of the audience rule collapsed into one.** The same
  test was spelled out in `chef_battle.access`, `config.battle_widget_context`,
  `config.hero_battle_panel` and `recipes.header_author`, so widening one left
  three disagreeing. All now call `is_battle_visible(request)`.
- "Become a Chef" in the account menu was offered to every author, gated only on
  not being enrolled. It is a Chef Battles entrance and led to a 404 for them; it
  now follows the same gate.
- Contract and AGENTS.md 8 corrected; both had said "staff/superuser".

## The mechanism that let it drift, and what now blocks it

The widening was justified at the time by a real symptom: the sitewide widget
advertised an entrance that 404'd. Two fixes existed — narrow the UI, or widen
the page. **The page was widened**, which is why a moderator ended up inside a
staff-only application.

`test_gate_parity` exists to hold the widget and the page together, and it did.
Its failure was that it asserted the *wrong shared value*. It now asserts the
Owner's three tiers by name, so agreement alone can no longer pass.

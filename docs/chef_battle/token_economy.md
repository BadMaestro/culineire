# TOKEN ECONOMY — CulinEire Platform Currency

## Author note
Defined by project creator.

> **SETTLED, X11, Owner 2026-08-10: THE DOCUMENT MATCHES THE CODE.** This is
> money, so it got said plainly: the four packages below were never what
> shipped. `chef_battle/token_config.py` (`TOKEN_PACKAGES`) is and has been the
> canonical source of truth — eight packages, standard price doubling each
> step, discount deepening from 0% to 40%. No price changed; the document is
> corrected to describe what a chef is actually charged.

---

## Token packages (purchase with real money via Stripe)

Canonical source: `chef_battle/token_config.py` → `TOKEN_PACKAGES`.

| # | Package | Tokens | Standard price | Discount | Price paid | Value |
|---|---------|--------|-----------------|----------|-------------|-------|
| 1 | Starter | 100 | €10.00 | 0% | €10.00 | €0.10/token |
| 2 | Chef | 200 | €20.00 | 10% | €18.00 | €0.09/token |
| 3 | Sous Chef | 400 | €40.00 | 20% | €32.00 | €0.08/token |
| 4 | Head Chef | 800 | €80.00 | 20% | €64.00 | €0.08/token |
| 5 | Executive | 1600 | €160.00 | 30% | €112.00 | €0.07/token |
| 6 | Master Chef | 3200 | €320.00 | 30% | €224.00 | €0.07/token |
| 7 | Culinary Master | 6400 | €640.00 | 40% | €384.00 | €0.06/token |
| 8 | Legend Chef | 12800 | €1280.00 | 40% | €768.00 | €0.06/token |

Larger packages = better value. Encourages bulk purchases.

---

## What tokens buy

> **SETTLED, X13, Owner 2026-08-10: A COMBAT ARTIFACT SENT INTO AN OPEN BATTLE
> COSTS DOUBLE, AND THAT IS THE RULE.** The second half is a delivery fee — the
> price of the right to make a gift while the fight is running. The table below
> listed only the artifact price and never named the fee. The prices themselves
> never changed and match `Artifact.RARITY_TOKEN_COST`; the totals are what a
> viewer is charged. Full account in `audience_gifts.md`.

| Action | Artifact price | Delivery fee | **Charged** |
|--------|----------------|--------------|-------------|
| Gift Common artifact into a live battle | 10 | 10 | **20 tokens** |
| Gift Uncommon artifact | 25 | 25 | **50 tokens** |
| Gift Rare artifact | 60 | 60 | **120 tokens** |
| Gift Epic artifact | 150 | 150 | **300 tokens** |
| **Buy an artifact for yourself** | shelf price | — | **10 / 25 / 60 / 150 tokens** |
| Gift Legendary artifact | — | — | **prize only, cannot be bought** |
| Appreciation gift (6 kinds, no fee) | 20–100 | — | **20–100 tokens** |
| **Arena chat sticker, on its own** | 10 | — | **10 tokens** |
| **The CulinEire Kitchen pack, all 13** | 100 | — | **100 tokens** |
| (Future) Extra battle slot | TBD | | |

**Stickers, AC-STK, Owner 2026-08-27.** The thirteen Arena chat stickers were
free from v2.5.1372 until this card; they are goods now. **The pack price is
FLAT** and that is his ruling rather than an implementation shortcut: a buyer
who already owns four still pays the full 100 and receives the missing nine —
*either all at once, or ten each*. **The pack's membership is frozen**: a
fourteenth sticker goes into a NEW pack, never into this one, because adding to
a pack that already has buyers silently enlarges what every one of them paid
for. Ownership is per chef and permanent, with no limit on use, and it is
enforced where a line is written rather than where one is read — every message
already in the database renders for everybody exactly as it did before.
A moderator may grant a sticker or a pack for nothing, from the moderation
panel, and that grant writes no token transaction because nobody paid.

**The Owner owns every sticker by RULE, not by granted rows** (his own choice,
2026-08-27, of the two put to him). Rows would have to be granted again for every
pack this project ever adds, and the day somebody forgets is the day his own
arena locks him out of it.

**Buying an artifact for yourself, AC-STK part B, Owner 2026-08-27.** His ruling:
*there has never been any ban on buying artifacts, and there never was one.* Four
acquisition routes, and only two of them were ever built:

1. **Won in battle** — `drop_battle_artifacts`, `source=DROP`. Built.
2. **Bought for yourself** at the shelf price, into your own chest, carried into a
   later battle. **No delivery fee** — the second half of a battle gift is the price
   of reaching a *running* fight, and nothing is running. `source=PURCHASED`,
   `tx_type=artifact_bought`, `LedgerEvent.ARTIFACT_PURCHASED`; those last two had
   existed since migration 0007 and were written by nothing until this card.
3. **Gifted to a chef BEFORE a battle**, at the shelf price with no delivery fee,
   because there is no running fight to influence. Ordinary property when it
   arrives — not locked, not forced, not expiring.
4. **Gifted DURING a battle** — buy and deliver in one move at double price, or pay
   the delivery half to send one you already own. The artifact is locked to that
   battle, must be used in it, and expires unused when it ends.

**Legendary is route 1 only.** Asked directly on 2026-08-27, the Owner ruled they
stay prize-only and cannot be bought — so every purchase and gift path refuses
them, in the same words, on purpose. **Duplicates are allowed**: `ChefArtifact` has
carried no uniqueness constraint since battle gifts needed to stack. A bought
artifact competes for the three-per-type combat loadout like anything else owned. The check is `is_owner_author()` — the same
`settings.OWNER_SLUG` read that `is_immortal()` and `check_owner_not_in_battle()`
already make — so the picker, the shop and the send path cannot disagree about who
he is. He is never charged for one either: `buy_sticker` and `buy_sticker_pack`
refuse him outright, because nothing the game does may take anything from his
account (AGENTS.md §18). It reaches that one account and no other.

---

## Rules

- Tokens are non-refundable once purchased
- Tokens do not expire
- Tokens are non-transferable between accounts
- Platform keeps 100% of token revenue (no cashout for users)
- Gifted artifacts go directly into the chef's battle inventory
- Gift appears publicly in battle chat: "🎁 @user gifted [Artifact] to Chef X!"

---

## Implementation notes

### Model: `TokenWallet`
- `user` OneToOneField
- `balance` IntegerField default=0

### Model: `TokenTransaction`
- `wallet` FK
- `amount` IntegerField (positive = credit, negative = debit)
- `transaction_type` choices: `purchase`, `gift_sent`, `refund`
- `reference` CharField (Stripe payment intent ID or gift ID)
- `created_at`

### Model: `TokenPackage`
- `name` CharField
- `tokens` IntegerField
- `price_eur` DecimalField
- `stripe_price_id` CharField
- `is_active` BooleanField

### Stripe integration
- One-time payment (not subscription)
- On `payment_intent.succeeded` webhook → credit wallet
- Reuse existing Stripe setup from sponsors app

### Packages actually shipped

Kept as data, not a Django model — see `chef_battle/token_config.py`:

```python
TOKEN_PACKAGES: list[TokenPackageSpec] = [
    {"key": "starter",          "name": "Starter",          "tokens": 100,   "standard_price_cents": 1000,   "discount_percent": 0,  "final_price_cents": 1000},
    {"key": "chef",             "name": "Chef",              "tokens": 200,   "standard_price_cents": 2000,   "discount_percent": 10, "final_price_cents": 1800},
    {"key": "sous_chef",        "name": "Sous Chef",         "tokens": 400,   "standard_price_cents": 4000,   "discount_percent": 20, "final_price_cents": 3200},
    {"key": "head_chef",        "name": "Head Chef",         "tokens": 800,   "standard_price_cents": 8000,   "discount_percent": 20, "final_price_cents": 6400},
    {"key": "executive",        "name": "Executive",         "tokens": 1600,  "standard_price_cents": 16000,  "discount_percent": 30, "final_price_cents": 11200},
    {"key": "master_chef",      "name": "Master Chef",       "tokens": 3200,  "standard_price_cents": 32000,  "discount_percent": 30, "final_price_cents": 22400},
    {"key": "culinary_master",  "name": "Culinary Master",   "tokens": 6400,  "standard_price_cents": 64000,  "discount_percent": 40, "final_price_cents": 38400},
    {"key": "legend_chef",      "name": "Legend Chef",       "tokens": 12800, "standard_price_cents": 128000, "discount_percent": 40, "final_price_cents": 76800},
]
```

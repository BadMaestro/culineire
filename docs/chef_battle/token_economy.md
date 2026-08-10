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
| Gift Legendary artifact | — | — | **prize only, cannot be bought** |
| Appreciation gift (6 kinds, no fee) | 20–100 | — | **20–100 tokens** |
| (Future) Profile cosmetics | TBD | | |
| (Future) Extra battle slot | TBD | | |

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

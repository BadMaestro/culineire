# TOKEN ECONOMY — CulinEire Platform Currency

## Author note
Defined by project creator.

---

## Token packages (purchase with real money via Stripe)

| Package | Tokens | Price | Value |
|---------|--------|-------|-------|
| Starter | 100 | €10 | €0.10/token |
| Popular | 250 | €20 | €0.08/token (20% bonus) |
| Pro | 600 | €40 | €0.067/token (40% bonus) |
| Champion | 1400 | €80 | €0.057/token (43% bonus) |

Larger packages = better value. Encourages bulk purchases.

---

## What tokens buy

| Action | Cost |
|--------|------|
| Gift Common artifact to a chef | 10 tokens |
| Gift Uncommon artifact | 25 tokens |
| Gift Rare artifact | 60 tokens |
| Gift Epic artifact | 150 tokens |
| Gift Legendary artifact | 400 tokens |
| (Future) Profile cosmetics | TBD |
| (Future) Extra battle slot | TBD |

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

### Packages to seed
```python
PACKAGES = [
    {"name": "Starter",  "tokens": 100,  "price_eur": 10},
    {"name": "Popular",  "tokens": 250,  "price_eur": 20},
    {"name": "Pro",      "tokens": 600,  "price_eur": 40},
    {"name": "Champion", "tokens": 1400, "price_eur": 80},
]
```

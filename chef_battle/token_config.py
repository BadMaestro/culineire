from __future__ import annotations

from decimal import Decimal
from typing import TypedDict


class TokenPackageSpec(TypedDict):
    key: str
    name: str
    tokens: int
    standard_price_cents: int
    discount_percent: int
    final_price_cents: int
    sort_order: int


# Canonical source of truth for all token packages.
# Base rate: 100 tokens = €10.00 (1000 cents).
# Tokens double at each step; standard price doubles accordingly.
# Discount tiers: slot 1=0%, slot 2=10%, slots 3-4=20%, slots 5-6=30%, slots 7-8=40%.
TOKEN_PACKAGES: list[TokenPackageSpec] = [
    {
        "key": "starter",
        "name": "Starter",
        "tokens": 100,
        "standard_price_cents": 1000,
        "discount_percent": 0,
        "final_price_cents": 1000,
        "sort_order": 1,
    },
    {
        "key": "chef",
        "name": "Chef",
        "tokens": 200,
        "standard_price_cents": 2000,
        "discount_percent": 10,
        "final_price_cents": 1800,
        "sort_order": 2,
    },
    {
        "key": "sous_chef",
        "name": "Sous Chef",
        "tokens": 400,
        "standard_price_cents": 4000,
        "discount_percent": 20,
        "final_price_cents": 3200,
        "sort_order": 3,
    },
    {
        "key": "head_chef",
        "name": "Head Chef",
        "tokens": 800,
        "standard_price_cents": 8000,
        "discount_percent": 20,
        "final_price_cents": 6400,
        "sort_order": 4,
    },
    {
        "key": "executive",
        "name": "Executive",
        "tokens": 1600,
        "standard_price_cents": 16000,
        "discount_percent": 30,
        "final_price_cents": 11200,
        "sort_order": 5,
    },
    {
        "key": "master_chef",
        "name": "Master Chef",
        "tokens": 3200,
        "standard_price_cents": 32000,
        "discount_percent": 30,
        "final_price_cents": 22400,
        "sort_order": 6,
    },
    {
        "key": "culinary_master",
        "name": "Culinary Master",
        "tokens": 6400,
        "standard_price_cents": 64000,
        "discount_percent": 40,
        "final_price_cents": 38400,
        "sort_order": 7,
    },
    {
        "key": "legend_chef",
        "name": "Legend Chef",
        "tokens": 12800,
        "standard_price_cents": 128000,
        "discount_percent": 40,
        "final_price_cents": 76800,
        "sort_order": 8,
    },
]

# Fast lookup by key
TOKEN_PACKAGES_BY_KEY: dict[str, TokenPackageSpec] = {p["key"]: p for p in TOKEN_PACKAGES}


def cents_to_eur(cents: int) -> Decimal:
    """Convert integer cents to Decimal euros with 2 decimal places."""
    return Decimal(cents) / Decimal(100)

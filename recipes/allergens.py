from __future__ import annotations

import re

EU_ALLERGENS = [
    {
        "key": "gluten",
        "label": "Cereals containing gluten",
        "aliases": [
            "gluten",
            "wheat",
            "barley",
            "rye",
            "oats",
            "spelt",
            "semolina",
            "breadcrumbs",
            "pasta",
            "bread",
            "flour",
        ],
    },
    {
        "key": "crustaceans",
        "label": "Crustaceans",
        "aliases": [
            "crustacean",
            "crustaceans",
            "prawn",
            "prawns",
            "shrimp",
            "crab",
            "lobster",
            "langoustine",
            "scampi",
            "crayfish",
        ],
    },
    {
        "key": "eggs",
        "label": "Eggs",
        "aliases": ["egg", "eggs", "mayonnaise", "mayo"],
    },
    {
        "key": "fish",
        "label": "Fish",
        "aliases": ["fish", "anchovy", "anchovies", "salmon", "tuna", "cod", "haddock", "sardine", "mackerel"],
    },
    {
        "key": "peanuts",
        "label": "Peanuts",
        "aliases": ["peanut", "peanuts"],
    },
    {
        "key": "soybeans",
        "label": "Soybeans",
        "aliases": ["soy", "soya", "soybean", "soybeans", "tofu", "miso", "tempeh", "edamame"],
    },
    {
        "key": "milk",
        "label": "Milk",
        "aliases": ["milk", "butter", "cream", "cheese", "yogurt", "yoghurt", "whey", "buttermilk"],
    },
    {
        "key": "tree_nuts",
        "label": "Tree nuts",
        "aliases": [
            "almond",
            "almonds",
            "hazelnut",
            "hazelnuts",
            "walnut",
            "walnuts",
            "cashew",
            "cashews",
            "pecan",
            "pecans",
            "pistachio",
            "pistachios",
            "macadamia",
            "brazil nut",
            "brazil nuts",
        ],
    },
    {
        "key": "celery",
        "label": "Celery",
        "aliases": ["celery", "celeriac"],
    },
    {
        "key": "mustard",
        "label": "Mustard",
        "aliases": ["mustard", "mustards"],
    },
    {
        "key": "sesame",
        "label": "Sesame",
        "aliases": ["sesame", "tahini"],
    },
    {
        "key": "sulphites",
        "label": "Sulphur dioxide / sulphites",
        "aliases": ["sulphite", "sulphites", "sulfite", "sulfites", "sulphur dioxide", "sulfur dioxide"],
    },
    {
        "key": "lupin",
        "label": "Lupin",
        "aliases": ["lupin", "lupine"],
    },
    {
        "key": "molluscs",
        "label": "Molluscs",
        "aliases": [
            "mollusc",
            "molluscs",
            "mussel",
            "mussels",
            "oyster",
            "oysters",
            "clam",
            "clams",
            "scallop",
            "scallops",
            "squid",
            "octopus",
            "cuttlefish",
            "snail",
            "whelk",
        ],
    },
]

EU_ALLERGEN_CHOICES = [(item["key"], item["label"]) for item in EU_ALLERGENS]
EU_ALLERGEN_KEYS = {item["key"] for item in EU_ALLERGENS}
EU_ALLERGEN_LABEL_TO_KEY = {item["label"].lower(): item["key"] for item in EU_ALLERGENS}


def parse_selected_allergen_keys(raw_value: str) -> list[str]:
    if not raw_value:
        return []

    parsed_keys: list[str] = []
    for part in re.split(r"[\n,;|]+", raw_value):
        normalized = part.strip().lower()
        if not normalized:
            continue
        if normalized in EU_ALLERGEN_KEYS:
            parsed_keys.append(normalized)
            continue
        if normalized in EU_ALLERGEN_LABEL_TO_KEY:
            parsed_keys.append(EU_ALLERGEN_LABEL_TO_KEY[normalized])

    if parsed_keys:
        return list(dict.fromkeys(parsed_keys))

    normalized_source = f" {re.sub(r'\s+', ' ', raw_value).lower()} "
    detected_keys: list[str] = []

    for allergen in EU_ALLERGENS:
        if any(
                re.search(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", normalized_source)
                for alias in allergen["aliases"]
        ):
            detected_keys.append(allergen["key"])

    return detected_keys


def serialize_allergen_keys(keys: list[str]) -> str:
    clean_keys = [key for key in keys if key in EU_ALLERGEN_KEYS]
    return "\n".join(dict.fromkeys(clean_keys))


def build_present_allergen_items(raw_value: str) -> list[dict]:
    selected_keys = set(parse_selected_allergen_keys(raw_value))
    return [
        {
            "key": item["key"],
            "label": item["label"],
            "is_present": item["key"] in selected_keys,
        }
        for item in EU_ALLERGENS
        if item["key"] in selected_keys
    ]

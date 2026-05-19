from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# ---------------------------------------------------------------------------
# Initial built-in word list (mirrors config/profanity.py _BUILTIN_WORDS).
# Update BOTH files if you change this list.
# ---------------------------------------------------------------------------
_BUILTIN_WORDS = [
    "fuck", "fucked", "fucker", "fucking", "fucks", "fuckin",
    "motherfucker", "motherfucking",
    "cunt", "cunts",
    "shit", "shits", "shitty", "shitting", "bullshit", "shite",
    "bitch", "bitches",
    "bastard", "bastards",
    "asshole", "assholes", "arsehole", "arseholes",
    "dickhead", "dickheads",
    "prick", "pricks",
    "wanker", "wankers", "wank", "wanking",
    "twat", "twats",
    "bollocks",
    "whore", "whores",
    "slut", "sluts",
    "nigger", "niggers", "nigga", "niggas",
    "kike", "kikes",
    "chink", "chinks",
    "spic", "spics",
    "gook", "gooks",
    "wetback", "wetbacks",
    "raghead", "ragheads",
    "towelhead",
    "zipperhead",
    "faggot", "faggots",
    "tranny", "trannies",
    "retard", "retarded", "retards",
    "spastic",
]


def seed_profanity_words(apps, schema_editor):
    ProfanityWord = apps.get_model("monitoring", "ProfanityWord")
    for word in _BUILTIN_WORDS:
        ProfanityWord.objects.get_or_create(
            word=word.lower(),
            defaults={"is_builtin": True},
        )


def remove_profanity_words(apps, schema_editor):
    """Reverse migration: remove only the seeded built-in words."""
    ProfanityWord = apps.get_model("monitoring", "ProfanityWord")
    ProfanityWord.objects.filter(is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0002_add_severity_to_security_event"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfanityWord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("word", models.CharField(db_index=True, help_text="Stored and matched in lowercase.", max_length=100, unique=True, verbose_name="Word")),
                ("is_builtin", models.BooleanField(default=False, help_text="Words seeded automatically from the initial system list.", verbose_name="Built-in")),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="profanity_words_added", to=settings.AUTH_USER_MODEL, verbose_name="Added by")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "Profanity word", "verbose_name_plural": "Profanity words", "ordering": ["word"]},
        ),
        migrations.RunPython(seed_profanity_words, remove_profanity_words),
    ]

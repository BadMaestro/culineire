from __future__ import annotations

from django import forms
from django.conf import settings
from django.utils import timezone

from recipes.models import Recipe, RecipeAuthor

from .models import BattleChallenge, BattleEntry


# X05, Owner 2026-08-06: twelve hours to answer a challenge, not forty-eight.
CHALLENGE_ACCEPTANCE_WINDOW = timezone.timedelta(hours=12)


class BattleChallengeForm(forms.ModelForm):
    class Meta:
        model = BattleChallenge
        fields = (
            "opponent", "task_kind", "contested_recipe", "theme_recipe",
            "theme", "battle_type", "message", "proposed_start_time",
        )
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
            "proposed_start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "task_kind": forms.RadioSelect,
        }

    def __init__(self, *args, challenger=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.challenger = challenger
        # T22: the Owner is outside the competition, so he is not offered as an
        # opponent. This is presentation only - the refusal that actually holds
        # is check_owner_not_in_battle() on the server, because a POST can name
        # any pk regardless of what the dropdown showed.
        self.fields["opponent"].queryset = (
            RecipeAuthor.objects.filter(user__isnull=False)
            .exclude(pk=getattr(challenger, "pk", None))
            .exclude(slug=settings.OWNER_SLUG)
            .order_by("name")
        )
        # Only an approved recipe can carry a battle: accepting the challenge
        # attaches this one as the challenger's entry, and the audience has to
        # be able to read what it is voting on.
        self.fields["theme_recipe"].queryset = Recipe.objects.filter(
            author=challenger, status=Recipe.Status.APPROVED, is_deleted=False
        ).order_by("-created_at")
        self.fields["theme_recipe"].required = True
        self.fields["theme_recipe"].label = "Your recipe for this battle"
        self.fields["theme_recipe"].help_text = "Your opponent will create or attach their own recipe after accepting."
        self.fields["theme"].widget.attrs.setdefault("placeholder", "Best Modern Irish Lamb Dish")
        # T19: the task the challenge carries. The recipe being contested is
        # the OPPONENT's, so it cannot be narrowed to one author until the
        # opponent is chosen - the queryset excludes the challenger's own
        # recipes and clean() enforces that it belongs to the chef named.
        self.fields["task_kind"].label = "What is this battle about?"
        self.fields["task_kind"].help_text = (
            "Say it plainly, and use the message below to describe what you are proposing."
        )
        self.fields["contested_recipe"].queryset = (
            Recipe.objects.filter(status=Recipe.Status.APPROVED, is_deleted=False)
            .exclude(author=challenger)
            .select_related("author")
            .order_by("author__name", "-created_at")
        )
        self.fields["contested_recipe"].required = False
        self.fields["contested_recipe"].label = "Their recipe you are contesting"
        self.fields["contested_recipe"].help_text = (
            "Only for a contested recipe. Leave blank when you are proposing a new one."
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "authoring-control")

    def clean_proposed_start_time(self):
        proposed = self.cleaned_data.get("proposed_start_time")
        if proposed and proposed < timezone.now():
            # T19, Owner 2026-08-15: there is no immediate battle any more.
            # Acceptance opens 48 hours of preparation, and a proposed time
            # inside that window is ignored in favour of it (accept_challenge).
            raise forms.ValidationError(
                "Choose a future start time, or leave this blank to start as soon as "
                "the 48-hour preparation window ends."
            )
        return proposed

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("task_kind")
        contested = cleaned.get("contested_recipe")
        opponent = cleaned.get("opponent")
        if kind == BattleChallenge.TaskKind.CONTEST_RECIPE:
            if not contested:
                self.add_error(
                    "contested_recipe",
                    "Choose the recipe of theirs you are contesting.",
                )
            elif opponent and contested.author_id != opponent.pk:
                self.add_error(
                    "contested_recipe",
                    "That recipe belongs to another chef. Choose one of your opponent's.",
                )
        elif contested:
            self.add_error(
                "contested_recipe",
                "A new-recipe challenge does not contest one of their recipes. "
                "Leave this blank, or switch the task above.",
            )
        return cleaned

    def save(self, commit=True):
        challenge = super().save(commit=False)
        challenge.challenger = self.challenger
        # X05, Owner 2026-08-06: A CHALLENGE STANDS FOR TWELVE HOURS.
        # battle_rules.md said 12 in its slot lifecycle and 48 in its own
        # first table; the code and the public rules page both said 48. He
        # ruled for 12: a challenge nobody answers should free the slot the
        # same day, not two days later.
        challenge.expires_at = timezone.now() + CHALLENGE_ACCEPTANCE_WINDOW
        if commit:
            challenge.save()
        return challenge


class BattleEntryForm(forms.ModelForm):
    content_type = forms.ChoiceField(
        choices=(("photo", "Photo Battle"), ("video", "Video Battle")),
        widget=forms.RadioSelect,
    )
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.none(), required=False)

    class Meta:
        model = BattleEntry
        fields = ("content_type", "recipe", "battle_statement")
        widgets = {
            "battle_statement": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, author=None, battle=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author
        self.battle = battle
        self._attached_recipe_id = self.instance.recipe_id if self.instance.pk else None
        self.fields["recipe"].queryset = Recipe.objects.filter(author=author, status=Recipe.Status.APPROVED, is_deleted=False).order_by("-created_at")
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.setdefault("class", "authoring-control")

    def clean(self):
        cleaned = super().clean()
        recipe = cleaned.get("recipe")

        if not recipe and not self._attached_recipe_id:
            self.add_error("recipe", "Choose a recipe for this battle.")
        elif self._attached_recipe_id and recipe and recipe.pk != self._attached_recipe_id:
            self.add_error("recipe", "The recipe is locked after you attach it for this battle.")
        return cleaned

    def save(self, commit=True):
        entry = super().save(commit=False)
        entry.author = self.author
        entry.battle = self.battle
        # G3: this radio has been on the form since it was written and its
        # answer went nowhere - `content_type` is declared here and does not
        # exist on the model, so every chef's choice was collected and dropped.
        # It sets the artifact tier on a win (chef_levels.md).
        chosen = self.cleaned_data.get("content_type")
        if chosen:
            entry.cooking_format = (
                BattleEntry.CookingFormat.WEBCAM if chosen == "video"
                else BattleEntry.CookingFormat.PHOTOS
            )
        if self._attached_recipe_id:
            entry.recipe_id = self._attached_recipe_id
        entry.dish_submitted_at = timezone.now()
        if commit:
            entry.full_clean()
            entry.save()
        return entry


class BattleRecipeAttachForm(forms.Form):
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.none(), label="Recipe for this battle")

    def __init__(self, *args, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recipe"].queryset = Recipe.objects.filter(
            author=author, status=Recipe.Status.APPROVED, is_deleted=False
        ).order_by("-created_at")
        self.fields["recipe"].widget.attrs["class"] = "authoring-control"

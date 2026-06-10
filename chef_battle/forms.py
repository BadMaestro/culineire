from __future__ import annotations

from django import forms
from django.utils import timezone

from articles.models import Article
from recipes.models import Recipe, RecipeAuthor

from .models import BattleChallenge, BattleEntry


class BattleChallengeForm(forms.ModelForm):
    class Meta:
        model = BattleChallenge
        fields = ("opponent", "theme", "battle_type", "message", "proposed_start_time")
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
            "proposed_start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, challenger=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.challenger = challenger
        self.fields["opponent"].queryset = RecipeAuthor.objects.filter(user__isnull=False).exclude(pk=getattr(challenger, "pk", None)).order_by("name")
        self.fields["theme"].widget.attrs.setdefault("placeholder", "Best Modern Irish Lamb Dish")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "authoring-control")

    def clean_proposed_start_time(self):
        proposed = self.cleaned_data.get("proposed_start_time")
        if proposed and proposed < timezone.now():
            raise forms.ValidationError("Choose a future start time, or leave this blank for an immediate battle.")
        return proposed

    def save(self, commit=True):
        challenge = super().save(commit=False)
        challenge.challenger = self.challenger
        challenge.expires_at = timezone.now() + timezone.timedelta(hours=48)
        if commit:
            challenge.save()
        return challenge


class BattleEntryForm(forms.ModelForm):
    content_type = forms.ChoiceField(
        choices=(("recipe", "Recipe"), ("article", "Article")),
        widget=forms.RadioSelect,
    )
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.none(), required=False)
    article = forms.ModelChoiceField(queryset=Article.objects.none(), required=False)

    class Meta:
        model = BattleEntry
        fields = ("content_type", "recipe", "article", "battle_statement")
        widgets = {
            "battle_statement": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, author=None, battle=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author
        self.battle = battle
        self.fields["recipe"].queryset = Recipe.objects.filter(author=author, status=Recipe.Status.APPROVED, is_deleted=False).order_by("-created_at")
        self.fields["article"].queryset = Article.objects.filter(author=author, status=Article.Status.APPROVED, is_deleted=False).order_by("-published")
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.setdefault("class", "authoring-control")

    def clean(self):
        cleaned = super().clean()
        content_type = cleaned.get("content_type")
        recipe = cleaned.get("recipe")
        article = cleaned.get("article")

        if content_type == "recipe" and not recipe:
            self.add_error("recipe", "Choose a recipe for this battle.")
        if content_type == "article" and not article:
            self.add_error("article", "Choose an article for this battle.")
        if content_type == "recipe":
            cleaned["article"] = None
        if content_type == "article":
            cleaned["recipe"] = None
        return cleaned

    def save(self, commit=True):
        entry = super().save(commit=False)
        entry.author = self.author
        entry.battle = self.battle
        if self.cleaned_data.get("content_type") == "recipe":
            entry.article = None
        else:
            entry.recipe = None
        if commit:
            entry.full_clean()
            entry.save()
        return entry

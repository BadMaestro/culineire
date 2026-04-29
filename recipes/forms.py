from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Recipe, RecipeAuthor


def _set_auth_widget_attrs(field, **attrs):
    field.widget.attrs.update(attrs)


class SignInForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _set_auth_widget_attrs(
            self.fields["username"],
            autocomplete="username",
            autofocus=True,
            placeholder="Enter your username",
        )
        _set_auth_widget_attrs(
            self.fields["password"],
            autocomplete="current-password",
            placeholder="Enter your password",
        )


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _set_auth_widget_attrs(
            self.fields["username"],
            autocomplete="username",
            autofocus=True,
            placeholder="Choose a username",
        )
        _set_auth_widget_attrs(
            self.fields["password1"],
            autocomplete="new-password",
            placeholder="Create a password",
        )
        _set_auth_widget_attrs(
            self.fields["password2"],
            autocomplete="new-password",
            placeholder="Repeat your password",
        )


class RecipeAuthoringForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = (
            "title",
            "short_description",
            "hero_image",
            "category",
            "difficulty",
            "prep_time_minutes",
            "cook_time_minutes",
            "servings",
            "calories",
            "ingredients",
            "method",
            "tips",
            "irish_context",
            "author_commentary",
            "source_type",
            "source_title",
            "source_author",
            "source_url",
            "source_note",
        )
        labels = {
            "title": "Recipe Title",
            "short_description": "Short Description",
            "hero_image": "Recipe Image",
            "prep_time_minutes": "Prep Time",
            "cook_time_minutes": "Cook Time",
            "servings": "Servings",
            "calories": "Calories",
            "ingredients": "Ingredients",
            "method": "Method",
            "tips": "Kitchen Tips",
            "irish_context": "Irish Context",
            "author_commentary": "Author Note",
            "source_type": "Source Type",
            "source_title": "Source Title",
            "source_author": "Source Author",
            "source_url": "Source URL",
            "source_note": "Source Note",
        }
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 3}),
            "ingredients": forms.Textarea(attrs={"rows": 8}),
            "method": forms.Textarea(attrs={"rows": 10}),
            "tips": forms.Textarea(attrs={"rows": 4}),
            "irish_context": forms.Textarea(attrs={"rows": 4}),
            "author_commentary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "authoring-control")

        for field_name in ("prep_time_minutes", "cook_time_minutes", "servings", "calories"):
            self.fields[field_name].widget.attrs.setdefault("min", "0")

        self.fields["title"].widget.attrs.setdefault("placeholder", "Cottage Pie")
        self.fields["short_description"].widget.attrs.setdefault(
            "placeholder",
            "A short card description for the recipe collection.",
        )
        self.fields["ingredients"].widget.attrs.setdefault(
            "placeholder",
            "One ingredient per line.",
        )
        self.fields["method"].widget.attrs.setdefault(
            "placeholder",
            "Write each step on a new line.",
        )


class RecipeAuthorProfileForm(forms.ModelForm):
    class Meta:
        model = RecipeAuthor
        fields = (
            "name",
            "slug",
            "bio",
            "avatar",
        )
        labels = {
            "name": "Author Name",
            "slug": "Profile URL Slug",
            "bio": "Short Bio",
            "avatar": "Author Avatar",
        }
        help_texts = {
            "slug": "Used in the public profile URL. Keep it short and readable.",
            "avatar": "Upload a square PNG or JPG for the best result.",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 5}),
            "avatar": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "authoring-control")

        self.fields["name"].widget.attrs.setdefault("placeholder", "GreenBear")
        self.fields["slug"].widget.attrs.setdefault("placeholder", "greenbear")
        self.fields["bio"].widget.attrs.setdefault(
            "placeholder",
            "A short note about your cooking style, background or kitchen focus.",
        )


class RecipeRatingForm(forms.Form):
    value = forms.IntegerField(min_value=1, max_value=5)

    def clean_value(self):
        value = self.cleaned_data["value"]
        if value < 1 or value > 5:
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return value


class RecipeCommentForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        strip=True,
    )
    content = forms.CharField(
        max_length=3000,
        widget=forms.Textarea,
        strip=True,
    )
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Name must be at least 2 characters long.")
        return name

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 5:
            raise forms.ValidationError("Comment is too short.")
        return content

    def clean_website(self):
        website = self.cleaned_data.get("website", "").strip()
        if website:
            raise forms.ValidationError("Spam detected.")
        return website

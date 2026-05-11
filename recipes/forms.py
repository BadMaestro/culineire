from django import forms


class _NoCurrentlyWidget(forms.ClearableFileInput):
    def is_initial(self, value):
        return False
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.safestring import mark_safe

from .models import ALLERGEN_CHOICES, Recipe, RecipeAuthor

_RULES_LABEL = mark_safe(
    'I have read and agree to the '
    '<a href="/legal/content-publishing-rules/" target="_blank" rel="noopener">Content Publishing Rules</a>.'
)
_OWN_WORK_LABEL = mark_safe(
    'This recipe is my own original work, a properly credited adaptation, '
    'or a family/personal recipe. I have not copied it from a book, '
    'website, or any other source without permission and attribution.'
)
_IMAGE_RIGHTS_LABEL = mark_safe(
    'All images I am uploading are either my own photos, '
    'correctly licensed, or in the public domain. '
    'I confirm I have <strong>not</strong> uploaded watermarked, '
    'stolen, or unlicensed images.'
)


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
    first_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            "autocomplete": "given-name",
            "placeholder": "First name (Optional)",
        }),
    )
    last_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            "autocomplete": "family-name",
            "placeholder": "Last name (Optional)",
        }),
    )
    default_avatar = forms.ChoiceField(
        required=True,
        choices=RecipeAuthor.DefaultAvatar.choices,
        initial=RecipeAuthor.DefaultAvatar.NEUTRAL,
        widget=forms.RadioSelect,
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "you@example.com (Mandatory)",
        }),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("first_name", "last_name", "username", "default_avatar", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _set_auth_widget_attrs(
            self.fields["username"],
            autocomplete="username",
            autofocus=True,
            placeholder="Choose a username (Mandatory)",
        )
        _set_auth_widget_attrs(
            self.fields["password1"],
            autocomplete="new-password",
            placeholder="Create a password (Mandatory)",
        )
        _set_auth_widget_attrs(
            self.fields["password2"],
            autocomplete="new-password",
            placeholder="Repeat your password (Mandatory)",
        )

        self.fields["username"].label = "Username"
        self.fields["first_name"].label = "First Name"
        self.fields["last_name"].label = "Last Name"
        self.fields["default_avatar"].label = "Choose Default Avatar"
        self.fields["email"].label = "Email Address"
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm Password"

        for field in self.fields.values():
            field.help_text = ""

    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()
        if value:
            raise forms.ValidationError("Spam detected.")
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class RecipeAuthoringForm(forms.ModelForm):
    additional_categories = forms.MultipleChoiceField(
        label="Additional Categories",
        choices=Recipe.Category.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "authoring-checkbox-list"}),
        help_text="Choose any extra categories this recipe should also appear in.",
    )

    allergens = forms.MultipleChoiceField(
        label="Allergens",
        choices=ALLERGEN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "authoring-checkbox-list"}),
        help_text=mark_safe(
            'Tick all allergens present in this recipe — '
            '<a href="https://www.fsai.ie/business-advice/starting-a-food-business/allergens" '
            'target="_blank" rel="noopener">FSAI / EU FIC 14 major allergens</a>.'
        ),
    )

    confirm_own_work = forms.BooleanField(
        label=_OWN_WORK_LABEL,
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "authoring-confirm-check"}),
    )
    confirm_image_rights = forms.BooleanField(
        label=_IMAGE_RIGHTS_LABEL,
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "authoring-confirm-check"}),
    )
    confirm_rules = forms.BooleanField(
        label=_RULES_LABEL,
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "authoring-confirm-check"}),
    )

    class Meta:
        model = Recipe
        fields = (
            "title",
            "short_description",
            "hero_image",
            "category",
            "additional_categories",
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
            "image_rights_status",
            "image_rights_note",
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
            "image_rights_status": "Image Rights",
            "image_rights_note": "Image Credit / Licence",
        }
        widgets = {
            "hero_image": _NoCurrentlyWidget(),
            "short_description": forms.Textarea(attrs={"rows": 3}),
            "ingredients": forms.Textarea(attrs={"rows": 8}),
            "method": forms.Textarea(attrs={"rows": 10}),
            "tips": forms.Textarea(attrs={"rows": 4}),
            "irish_context": forms.Textarea(attrs={"rows": 4}),
            "author_commentary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if field_name not in ("confirm_own_work", "confirm_image_rights", "confirm_rules",
                                  "additional_categories", "allergens"):
                field.widget.attrs.setdefault("class", "authoring-control")

        self.fields["additional_categories"].initial = self.instance.get_additional_category_values()

        # For new recipes: don't pre-select the model default — force explicit choice.
        # For existing recipes: leave the saved value as-is.
        if not self.instance.pk:
            self.fields["category"].choices = [("", "— Select a category —")] + list(Recipe.Category.choices)
            self.initial["category"] = ""

        if self.instance.pk and self.instance.allergens:
            self.fields["allergens"].initial = [
                a.strip() for a in self.instance.allergens.split(",") if a.strip()
            ]

        # Pre-check confirmation boxes if author already agreed previously
        if self.instance.pk:
            if self.instance.confirmed_own_work:
                self.fields["confirm_own_work"].initial = True
            if self.instance.confirmed_image_rights:
                self.fields["confirm_image_rights"].initial = True
            if self.instance.confirmed_rules:
                self.fields["confirm_rules"].initial = True

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
        self.fields["hero_image"].widget.attrs.setdefault("accept", ".jpg,.jpeg,.png,.webp")
        self.fields["image_rights_note"].widget.attrs.setdefault(
            "placeholder",
            "Licence name",
        )

    def clean_additional_categories(self):
        selected = []
        primary_category = self.cleaned_data.get("category")

        for value in self.cleaned_data.get("additional_categories", []):
            if value == primary_category or value in selected:
                continue
            selected.append(value)

        return selected

    def save_additional_categories(self, recipe):
        selected = self.cleaned_data.get("additional_categories", [])
        recipe.additional_category_links.exclude(category__in=selected).delete()

        existing = set(recipe.additional_category_links.values_list("category", flat=True))
        for category_value in selected:
            if category_value not in existing:
                recipe.additional_category_links.create(category=category_value)

    def save(self, commit=True, confirmed_by=None):
        from django.utils import timezone

        instance = super().save(commit=False)
        instance.allergens = ",".join(self.cleaned_data.get("allergens", []))
        instance.confirmed_own_work = bool(self.cleaned_data.get("confirm_own_work"))
        instance.confirmed_image_rights = bool(self.cleaned_data.get("confirm_image_rights"))
        instance.confirmed_rules = bool(self.cleaned_data.get("confirm_rules"))
        instance.confirmation_timestamp = timezone.now()
        if confirmed_by is not None:
            instance.confirmed_by = confirmed_by

        if commit:
            instance.save()
            self.save_additional_categories(instance)

        return instance


class RecipeAuthorProfileForm(forms.ModelForm):
    class Meta:
        model = RecipeAuthor
        fields = (
            "name",
            "default_avatar",
            "bio",
            "avatar",
        )
        labels = {
            "name": "Author Name",
            "default_avatar": "Choose Default Avatar",
            "bio": "Short Bio",
            "avatar": "Author Avatar",
        }
        help_texts = {
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
        self.fields["bio"].widget.attrs.setdefault(
            "placeholder",
            "A short note about your cooking style, background or kitchen focus.",
        )
        self.fields["avatar"].widget.attrs.setdefault("accept", ".jpg,.jpeg,.png,.webp")


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

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.safestring import mark_safe

from recipes.models import RecipeAuthor


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
    # Filled by the "More" gallery, which is a picker over the same three-radio
    # field: the person opens it and chooses a portrait. Optional by design and
    # never written for him -- see recipes/avatar_gallery.py for why.
    gallery_avatar = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gallery_avatar"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "you@example.com (Mandatory)",
        }),
    )

    def clean_gallery_avatar(self):
        """Accept only a real gallery key.

        The field is hidden, which means it is exactly as editable as anything
        else a client sends. Validating against the named set keeps a hand-made
        POST from writing an arbitrary string that later renders as a broken
        image on every page the author appears on.
        """
        from recipes.avatar_gallery import is_gallery_key

        value = (self.cleaned_data.get("gallery_avatar") or "").strip()
        if not value:
            return ""
        if not is_gallery_key(value):
            raise forms.ValidationError("Choose a portrait from the gallery.")
        return value

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

    def clean_username(self):
        # Sign-in matches the username without regard to case, so two accounts
        # differing only in case would both answer to one login and the backend
        # could not tell which was meant. The taken name keeps whatever case its
        # owner chose; only a case-variant of it is refused here.
        username = self.cleaned_data.get("username", "").strip()
        User = get_user_model()
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "This username is already taken. Usernames are not "
                "case-sensitive, so a different capitalisation of an existing "
                "name is the same name."
            )
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists. "
                "Please sign in or use a different email."
            )
        return email

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

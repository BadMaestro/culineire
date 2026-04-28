from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


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

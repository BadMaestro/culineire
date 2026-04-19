from django import forms


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

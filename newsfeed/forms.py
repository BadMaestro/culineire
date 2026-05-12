from django import forms

from .models import NewsFeedEntry


class NewsFeedEntryForm(forms.ModelForm):
    class Meta:
        model = NewsFeedEntry
        fields = ["entry_type", "title", "message", "url", "version", "published_at", "is_public"]
        widgets = {
            "entry_type": forms.Select(attrs={"class": "authoring-control"}),
            "title": forms.TextInput(attrs={"class": "authoring-control", "placeholder": "Entry title"}),
            "message": forms.Textarea(attrs={"class": "authoring-control", "rows": 4, "placeholder": "Optional description or detail"}),
            "url": forms.URLInput(attrs={"class": "authoring-control", "placeholder": "https://"}),
            "version": forms.TextInput(attrs={"class": "authoring-control", "placeholder": "e.g. 1.4.19"}),
            "published_at": forms.DateTimeInput(
                attrs={"class": "authoring-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "is_public": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].required = False
        self.fields["url"].required = False
        self.fields["version"].required = False
        self.fields["published_at"].input_formats = ["%Y-%m-%dT%H:%M"]

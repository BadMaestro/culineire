from django import forms

from config.profanity import find_profanity
from .models import ContentReport


class ContentReportForm(forms.ModelForm):
    class Meta:
        model = ContentReport
        fields = (
            "reporter_name",
            "reporter_email",
            "organisation",
            "report_type",
            "reported_url",
            "evidence_url",
            "description",
            "good_faith_confirmed",
        )
        labels = {
            "reporter_name": "Your Name",
            "reporter_email": "Your Email Address",
            "organisation": "Organisation (optional)",
            "report_type": "Type of Issue",
            "reported_url": "URL of the Affected Page",
            "evidence_url": "Link to Original Source or Evidence (optional)",
            "description": "Description",
            "good_faith_confirmed": (
                "I confirm this report is made in good faith and the information "
                "provided is accurate to the best of my knowledge."
            ),
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "data-profanity": ""}),
        }

    # Honeypot
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, initial_name=None, initial_email=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs.setdefault("class", "authoring-control")
        self.fields["reported_url"].widget.attrs["placeholder"] = (
            "https://culineire.ie/recipes/..."
        )
        self.fields["evidence_url"].widget.attrs["placeholder"] = (
            "https://example.com/original-source"
        )
        self.fields["description"].widget.attrs["placeholder"] = (
            "Describe the issue. Include the original source URL or other evidence where possible."
        )
        # Pre-populate for authenticated users
        if initial_name:
            self.fields["reporter_name"].initial = initial_name
        if initial_email:
            self.fields["reporter_email"].initial = initial_email

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()
        if value:
            raise forms.ValidationError("Spam detected.")
        return value

    def clean_description(self):
        text = self.cleaned_data.get("description", "") or ""
        bad = find_profanity(text)
        if bad:
            quoted = ", ".join(f'"{w}"' for w in bad)
            raise forms.ValidationError(f"Contains forbidden words: {quoted}.")
        return text

    def clean_good_faith_confirmed(self):
        value = self.cleaned_data.get("good_faith_confirmed", False)
        if not value:
            raise forms.ValidationError(
                "You must confirm that this report is made in good faith before submitting."
            )
        return value

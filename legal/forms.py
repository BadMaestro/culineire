from django import forms

from .models import ContentReport


class ContentReportForm(forms.ModelForm):
    class Meta:
        model = ContentReport
        fields = (
            "report_type",
            "reported_url",
            "description",
        )
        labels = {
            "report_type": "Type of Issue",
            "reported_url": "URL of the Affected Page",
            "description": "Description",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "authoring-control")
        self.fields["reported_url"].widget.attrs["placeholder"] = "https://culineire.ie/recipes/..."
        self.fields["description"].widget.attrs["placeholder"] = (
            "Describe the issue. Include original source URL or other evidence where possible."
        )

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()
        if value:
            raise forms.ValidationError("Spam detected.")
        return value

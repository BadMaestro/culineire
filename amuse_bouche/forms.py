from django import forms
from django.utils.safestring import mark_safe

from config.profanity import find_profanity
from .models import AmuseBouche


class _NoCurrentlyWidget(forms.ClearableFileInput):
    def is_initial(self, value):
        return False


_RULES_LABEL = mark_safe(
    'I have read and agree to the '
    '<a href="/legal/content-publishing-rules/" target="_blank" rel="noopener">Content Publishing Rules</a>.'
)
_OWN_WORK_LABEL = mark_safe(
    "This Amuse-Bouche is my own original work or a properly credited adaptation."
)
_IMAGE_RIGHTS_LABEL = mark_safe(
    "All images I am uploading are either my own photos, correctly licensed, or in the public domain."
)


class AmuseBoucheAuthoringForm(forms.ModelForm):
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
        model = AmuseBouche
        fields = (
            "title",
            "short_description",
            "content_type",
            "cover_image",
            "cover_image_alt",
            "linked_recipe",
            "linked_article",
            "allow_comments",
            "seo_title",
            "seo_description",
        )
        widgets = {
            "cover_image": _NoCurrentlyWidget(),
            "short_description": forms.Textarea(attrs={"rows": 4}),
            "seo_description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author
        if author:
            self.fields["linked_recipe"].queryset = author.recipes.filter(status="approved", is_deleted=False)
            self.fields["linked_article"].queryset = author.articles.filter(status="approved", is_deleted=False)
        else:
            self.fields["linked_recipe"].queryset = self.fields["linked_recipe"].queryset.none()
            self.fields["linked_article"].queryset = self.fields["linked_article"].queryset.none()

        _skip = {"confirm_own_work", "confirm_image_rights", "confirm_rules"}
        _text_widgets = (forms.TextInput, forms.Textarea)
        for field_name, field in self.fields.items():
            if field_name not in _skip:
                field.widget.attrs.setdefault("class", "authoring-control")
            if field_name not in _skip and isinstance(field.widget, _text_widgets):
                field.widget.attrs.setdefault("data-profanity", "")
        self.fields["cover_image"].widget.attrs.setdefault("accept", ".jpg,.jpeg,.png,.webp")

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ("title", "short_description", "cover_image_alt", "seo_title", "seo_description"):
            matches = find_profanity(cleaned_data.get(field_name, ""))
            if matches:
                self.add_error(field_name, "Please remove inappropriate language before submitting.")
        return cleaned_data

from django import forms
from django.utils import timezone
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
        required=False,   # optional when no image uploaded
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
            "content_type",
            "short_description",
            "cover_image",
            "cover_image_alt",
            "image_rights_status",
            "image_rights_note",
            "source_type",
            "source_title",
            "source_author",
            "source_url",
            "source_note",
            "linked_recipe",
            "linked_article",
            "allow_comments",
            "seo_title",
            "seo_description",
        )
        widgets = {
            "cover_image": _NoCurrentlyWidget(),
            "short_description": forms.Textarea(attrs={"rows": 4}),
            "source_note": forms.Textarea(attrs={"rows": 2}),
            "seo_description": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "cover_image": "Cover Image",
            "cover_image_alt": "Cover Image Alt Text",
            "image_rights_status": "Image Rights",
            "image_rights_note": "Image Credit / Licence",
            "source_type": "Source Type",
            "source_title": "Source Title",
            "source_author": "Source Author",
            "source_url": "Source URL",
            "source_note": "Source Note",
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

        # Pre-check confirmations if author already agreed previously
        if self.instance.pk:
            if self.instance.confirmed_own_work:
                self.fields["confirm_own_work"].initial = True
            if self.instance.confirmed_image_rights:
                self.fields["confirm_image_rights"].initial = True
            if self.instance.confirmed_rules:
                self.fields["confirm_rules"].initial = True

        _skip = {"confirm_own_work", "confirm_image_rights", "confirm_rules"}
        _text_widgets = (forms.TextInput, forms.Textarea)
        for field_name, field in self.fields.items():
            if field_name not in _skip:
                field.widget.attrs.setdefault("class", "authoring-control")
            if field_name not in _skip and isinstance(field.widget, _text_widgets):
                field.widget.attrs.setdefault("data-profanity", "")

        self.fields["cover_image"].widget.attrs.setdefault("accept", ".jpg,.jpeg,.png,.webp")
        self.fields["image_rights_note"].widget.attrs.setdefault("placeholder", "Licence name or credit line")
        self.fields["title"].widget.attrs.setdefault("placeholder", "e.g. Brown Butter Oat Crumble")
        self.fields["short_description"].widget.attrs.setdefault(
            "placeholder", "A short description shown on your card and in the feed.",
        )
        self.fields["source_title"].widget.attrs.setdefault("placeholder", "e.g. Ballymaloe Cookery Course")
        self.fields["source_author"].widget.attrs.setdefault("placeholder", "e.g. Darina Allen")
        self.fields["source_url"].widget.attrs.setdefault("placeholder", "https://")
        self.fields["source_note"].widget.attrs.setdefault(
            "placeholder", "Any additional attribution or context."
        )

    def clean(self):
        cleaned_data = super().clean()

        image_rights_status = cleaned_data.get("image_rights_status")
        image_rights_note = (cleaned_data.get("image_rights_note") or "").strip()
        cover_image = cleaned_data.get("cover_image")

        # If image rights require a credit/licence note, enforce it
        if (
            image_rights_status in {
                AmuseBouche.ImageRightsStatus.LICENSED,
                AmuseBouche.ImageRightsStatus.PUBLIC_DOMAIN,
            }
            and not image_rights_note
        ):
            self.add_error(
                "image_rights_note",
                "Add the licence, credit line, or permission reference for this image status.",
            )

        # Require image-rights confirmation when an image is being uploaded
        if cover_image and not cleaned_data.get("confirm_image_rights"):
            self.add_error(
                "confirm_image_rights",
                "Please confirm your image rights before uploading.",
            )

        # Source attribution: non-original content requires title or URL
        source_type = cleaned_data.get("source_type")
        source_title = (cleaned_data.get("source_title") or "").strip()
        source_url = (cleaned_data.get("source_url") or "").strip()
        if source_type and source_type not in {
            AmuseBouche.SourceType.ORIGINAL,
            AmuseBouche.SourceType.AI_ASSISTED,
        }:
            if not source_title and not source_url:
                self.add_error(
                    "source_title",
                    "Please provide a source title or URL for this type of content.",
                )

        # Profanity check
        for field_name in (
            "title", "short_description", "cover_image_alt",
            "source_title", "source_author", "source_note",
            "seo_title", "seo_description",
        ):
            matches = find_profanity(cleaned_data.get(field_name, "") or "")
            if matches:
                self.add_error(field_name, "Please remove inappropriate language before submitting.")

        return cleaned_data

    def save(self, commit=True, confirmed_by=None):
        instance = super().save(commit=False)
        instance.confirmed_own_work = bool(self.cleaned_data.get("confirm_own_work"))
        instance.confirmed_image_rights = bool(self.cleaned_data.get("confirm_image_rights"))
        instance.confirmed_rules = bool(self.cleaned_data.get("confirm_rules"))
        instance.confirmation_timestamp = timezone.now()
        if confirmed_by is not None:
            instance.confirmed_by = confirmed_by
        if commit:
            instance.save()
        return instance

from __future__ import annotations

from django import forms
from django.utils import timezone

from .models import SponsorApplication

DECLARATION_TEXTS = [
    "I confirm that I have the right to use this logo/avatar and that Bearcave Limited may display it on CulinEire if the sponsorship is approved and published.",
    "I accept the CulinEire Annual Ring Sponsorship Terms and understand that payment reserves the selected spot for review only. Payment does not guarantee approval, publication or activation.",
    "I confirm, to the best of my knowledge, that neither I, nor any company, organisation or business I represent, nor any relevant owner, director, beneficial owner or controlling person, is subject to EU, UN, Irish or other applicable financial sanctions. I also confirm that I am not applying on behalf of, for the benefit of, or under the control of any sanctioned person, company, organisation or body.",
]


class SponsorApplicationForm(forms.ModelForm):
    logo_rights_confirmed = forms.BooleanField(required=True)
    terms_accepted = forms.BooleanField(required=True)
    # sanctions_declaration_1 is a form-only field; stored in SponsorApplicantDeclaration, not the model
    sanctions_declaration_1 = forms.BooleanField(required=True)

    class Meta:
        model = SponsorApplication
        fields = [
            "sponsor_name",
            "contact_name",
            "email",
            "phone",
            "website_url",
            "logo",
            "sponsor_note",
            "logo_offset_x",
            "logo_offset_y",
            "logo_scale",
            "logo_rotation",
            "logo_rights_confirmed",
            "terms_accepted",
        ]
        labels = {
            "sponsor_name": "Sponsor display name",
            "website_url": "Website or profile URL",
            "logo": "Logo or avatar",
            "logo_offset_x": "Image horizontal offset",
            "logo_offset_y": "Image vertical offset",
            "logo_scale": "Image scale",
            "logo_rotation": "Image rotation (degrees)",
        }

    def clean_website_url(self):
        url = (self.cleaned_data.get("website_url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def _clean_image_offset(self, field_name):
        offset = self.cleaned_data.get(field_name) or 0.0
        if offset < -200 or offset > 200:
            raise forms.ValidationError("Image position must stay within the editable cell preview.")
        return offset

    def clean_logo_offset_x(self):
        return self._clean_image_offset("logo_offset_x")

    def clean_logo_offset_y(self):
        return self._clean_image_offset("logo_offset_y")

    def clean_logo_scale(self):
        scale = self.cleaned_data.get("logo_scale") or 1.0
        if scale < 0.2 or scale > 3.0:
            raise forms.ValidationError("Image scale must be between 0.2 and 3.0.")
        return scale

    def clean_logo_rotation(self):
        rotation = self.cleaned_data.get("logo_rotation") or 0.0
        # Normalise to [0, 360)
        return float(rotation) % 360

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("terms_accepted"):
            cleaned["terms_accepted_at"] = timezone.now()
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("terms_accepted"):
            instance.terms_accepted_at = self.cleaned_data.get("terms_accepted_at") or timezone.now()
            instance.terms_version = SponsorApplication.TERMS_VERSION
            # approval_acknowledged is combined with terms acceptance in the public form
            instance.approval_acknowledged = True
        if commit:
            instance.save()
        return instance

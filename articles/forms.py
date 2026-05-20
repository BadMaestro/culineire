from django import forms
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify

from config.profanity import find_profanity
from .models import Article


class _NoCurrentlyWidget(forms.ClearableFileInput):
    def is_initial(self, value):
        return False

_RULES_LABEL = mark_safe(
    'I have read and agree to the '
    '<a href="/legal/content-publishing-rules/" target="_blank" rel="noopener">Content Publishing Rules</a>.'
)
_OWN_WORK_LABEL = mark_safe(
    'This article is my own original writing or a properly credited adaptation. '
    'I have not copied it from a publication, website, or any other source without permission and attribution.'
)
_IMAGE_RIGHTS_LABEL = mark_safe(
    'All images I am uploading are either my own photos, '
    'correctly licensed, or in the public domain. '
    'I confirm I have <strong>not</strong> uploaded watermarked, '
    'stolen, or unlicensed images. '
    'See the <a href="/legal/copyright-image-rights-guide/" target="_blank" rel="noopener">Copyright and Image Rights Guide</a>.'
)


def _generate_unique_article_slug(title: str, instance=None) -> str:
    base_slug = slugify(title)[:180] or "article"
    slug = base_slug
    counter = 2

    queryset = Article.objects.all()
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:200 - len(suffix)]}{suffix}"
        counter += 1

    return slug


class ArticleAuthoringForm(forms.ModelForm):

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
        model = Article
        fields = (
            "title",
            "excerpt",
            "hero_image",
            "published",
            "related_recipe",
            "body",
            "image_rights_status",
            "image_rights_note",
            "source_type",
            "source_title",
            "source_author",
            "source_url",
            "source_note",
        )
        labels = {
            "title": "Article Title",
            "excerpt": "Short Description",
            "hero_image": "Article Image",
            "published": "Publishing Date",
            "related_recipe": "Related Recipe",
            "body": "Article Body",
            "image_rights_status": "Image Rights",
            "image_rights_note": "Image Credit / Licence",
            "source_type": "Source Type",
            "source_title": "Source Title",
            "source_author": "Source Author",
            "source_url": "Source URL",
            "source_note": "Source Note",
        }
        widgets = {
            "hero_image": _NoCurrentlyWidget(),
            "published": forms.DateInput(attrs={"type": "date"}),
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "body": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author
        effective_author = author or getattr(self.instance, "author", None)

        if effective_author:
            self.fields["related_recipe"].queryset = effective_author.recipes.order_by("-created_at")
        else:
            self.fields["related_recipe"].queryset = self.fields["related_recipe"].queryset.none()

        self.fields["published"].initial = self.fields["published"].initial or timezone.localdate()
        self.fields["related_recipe"].required = False

        _skip = {"confirm_own_work", "confirm_image_rights", "confirm_rules"}
        _text_widgets = (forms.TextInput, forms.Textarea)
        for field_name, field in self.fields.items():
            if field_name not in _skip:
                field.widget.attrs.setdefault("class", "authoring-control")
            if field_name not in _skip and isinstance(field.widget, _text_widgets):
                field.widget.attrs.setdefault("data-profanity", "")

        self.fields["title"].widget.attrs.setdefault(
            "placeholder", "How To Make Perfect Irish Potato Soup",
        )
        self.fields["excerpt"].widget.attrs.setdefault(
            "placeholder", "A short card description for the article collection.",
        )
        self.fields["body"].widget.attrs.setdefault(
            "placeholder", "Write the article here.",
        )
        self.fields["image_rights_note"].widget.attrs.setdefault(
            "placeholder", "Licence name",
        )
        self.fields["hero_image"].widget.attrs.setdefault("accept", ".jpg,.jpeg,.png,.webp")

        # Pre-check confirmations on edit if already agreed
        if self.instance.pk:
            if self.instance.confirmed_own_work:
                self.fields["confirm_own_work"].initial = True
            if self.instance.confirmed_image_rights:
                self.fields["confirm_image_rights"].initial = True
            if self.instance.confirmed_rules:
                self.fields["confirm_rules"].initial = True

    # ── Profanity validation (all text fields in one pass) ────────────────

    def clean(self):
        cleaned_data = super().clean()
        image_rights_status = cleaned_data.get("image_rights_status")
        image_rights_note = (cleaned_data.get("image_rights_note") or "").strip()
        source_type = cleaned_data.get("source_type")
        source_title = (cleaned_data.get("source_title") or "").strip()
        source_author = (cleaned_data.get("source_author") or "").strip()
        source_url = (cleaned_data.get("source_url") or "").strip()
        source_note = (cleaned_data.get("source_note") or "").strip()
        hero_image = cleaned_data.get("hero_image") or getattr(self.instance, "hero_image", None)
        active_gallery_exists = (
            self.instance.pk
            and self.instance.gallery_images.filter(is_active=True).exists()
        )

        if (
            image_rights_status in {
                Article.ImageRightsStatus.LICENSED,
                Article.ImageRightsStatus.PUBLIC_DOMAIN,
            }
            and not image_rights_note
        ):
            self.add_error(
                "image_rights_note",
                "Add the licence, credit line, or permission reference for this image status.",
            )

        if (
            image_rights_status == Article.ImageRightsStatus.NOT_APPLICABLE
            and (hero_image or active_gallery_exists)
        ):
            self.add_error(
                "image_rights_status",
                "Choose the correct image rights status when an article image is attached.",
            )

        if source_type == Article.SourceType.ADAPTED and not source_title:
            self.add_error(
                "source_title",
                "Add the source title for adapted articles.",
            )

        if (
            source_type == Article.SourceType.INSPIRED
            and not any([source_title, source_author, source_url, source_note])
        ):
            self.add_error(
                "source_note",
                "Add at least one source detail for inspired articles.",
            )

        _text_widgets = (forms.TextInput, forms.Textarea)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, _text_widgets):
                continue
            value = cleaned_data.get(field_name, "")
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                continue
            text = value
            bad = find_profanity(text)
            if bad:
                quoted = ", ".join(f'"{w}"' for w in bad)
                self.add_error(
                    field_name,
                    f"Contains forbidden words: {quoted}. Please remove them before publishing.",
                )
        return cleaned_data

    def save(self, commit=True, confirmed_by=None):
        article = super().save(commit=False)

        if self.author and not article.pk:
            article.author = self.author

        if not article.slug:
            article.slug = _generate_unique_article_slug(article.title, article)

        article.confirmed_own_work = bool(self.cleaned_data.get("confirm_own_work"))
        article.confirmed_image_rights = bool(self.cleaned_data.get("confirm_image_rights"))
        article.confirmed_rules = bool(self.cleaned_data.get("confirm_rules"))
        article.confirmation_timestamp = timezone.now()
        if confirmed_by is not None:
            article.confirmed_by = confirmed_by

        if commit:
            article.save()
            self.save_m2m()

        return article

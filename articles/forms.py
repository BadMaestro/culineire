from django import forms
from django.utils import timezone
from django.utils.text import slugify

from .models import Article


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
    class Meta:
        model = Article
        fields = (
            "title",
            "excerpt",
            "hero_image",
            "published",
            "related_recipe",
            "body",
        )
        labels = {
            "title": "Article Title",
            "excerpt": "Short Description",
            "hero_image": "Article Image",
            "published": "Publishing Date",
            "related_recipe": "Related Recipe",
            "body": "Article Body",
        }
        widgets = {
            "published": forms.DateInput(attrs={"type": "date"}),
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "body": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author

        if author:
            self.fields["related_recipe"].queryset = author.recipes.order_by("-created_at")
        else:
            self.fields["related_recipe"].queryset = self.fields["related_recipe"].queryset.none()

        self.fields["published"].initial = self.fields["published"].initial or timezone.localdate()
        self.fields["related_recipe"].required = False

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "authoring-control")

        self.fields["title"].widget.attrs.setdefault(
            "placeholder",
            "How To Make Perfect Irish Potato Soup",
        )
        self.fields["excerpt"].widget.attrs.setdefault(
            "placeholder",
            "A short card description for the article collection.",
        )
        self.fields["body"].widget.attrs.setdefault(
            "placeholder",
            "Write the article here.",
        )
        self.fields["hero_image"].widget.attrs.setdefault("accept", ".jpg,.jpeg,.png,.webp")

    def save(self, commit=True):
        article = super().save(commit=False)

        if self.author:
            article.author = self.author

        if not article.slug:
            article.slug = _generate_unique_article_slug(article.title, article)

        if commit:
            article.save()
            self.save_m2m()

        return article

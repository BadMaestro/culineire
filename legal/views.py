from django.shortcuts import render
from django.views.generic import TemplateView

from .forms import ContentReportForm


class LegalHubView(TemplateView):
    template_name = "legal/legal_hub.html"


class ContentPublishingRulesView(TemplateView):
    template_name = "legal/content_publishing_rules.html"


class AuthorSubmissionAgreementView(TemplateView):
    template_name = "legal/author_submission_agreement.html"


class CopyrightImageRightsGuideView(TemplateView):
    template_name = "legal/copyright_image_rights_guide.html"


def report_content(request):
    submitted = False
    form = ContentReportForm()

    if request.method == "POST":
        form = ContentReportForm(request.POST)
        if form.is_valid():
            form.save()
            submitted = True
            form = ContentReportForm()

    return render(request, "legal/report_content.html", {
        "form": form,
        "submitted": submitted,
    })

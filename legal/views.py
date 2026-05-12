import logging

from django.conf import settings
from django.core.mail import BadHeaderError
from config.email_utils import send_template_mail
from django.shortcuts import render
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from config.turnstile import verify_turnstile

from .forms import ContentReportForm

logger = logging.getLogger(__name__)


class LegalHubView(TemplateView):
    template_name = "legal/legal_hub.html"


class ContentPublishingRulesView(TemplateView):
    template_name = "legal/content_publishing_rules.html"


class AuthorSubmissionAgreementView(TemplateView):
    template_name = "legal/author_submission_agreement.html"


class CopyrightImageRightsGuideView(TemplateView):
    template_name = "legal/copyright_image_rights_guide.html"


def _send_report_notification(report):
    notify_email = getattr(settings, "REPORT_NOTIFY_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
    if not notify_email:
        return

    admin_url = (
        f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}"
        f"/cave19850324/legal/contentreport/{report.pk}/change/"
    )
    subject = f"[CulinEire] New content report: {report.get_report_type_display()}"
    message = (
        f"A new content report has been submitted.\n\n"
        f"Type: {report.get_report_type_display()}\n"
        f"From: {report.reporter_name} <{report.reporter_email}>\n"
        f"URL reported: {report.reported_url or 'not provided'}\n\n"
        f"Description:\n{report.description}\n\n"
        f"Admin: {admin_url}\n"
    )
    try:
        send_template_mail(
            subject=subject,
            template="content_report",
            context={"report": report, "admin_url": admin_url},
            recipient_list=[notify_email],
            fail_silently=True,
        )
    except BadHeaderError:
        logger.warning("BadHeaderError sending report notification for report %s", report.pk)


@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def report_content(request):
    submitted = False
    form = ContentReportForm()
    turnstile_error = False

    if request.method == "POST":
        if getattr(request, "limited", False):
            return render(request, "legal/report_content.html", {
                "form": form,
                "submitted": False,
                "turnstile_error": False,
                "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
                "rate_limited": True,
            })

        form = ContentReportForm(request.POST)
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            turnstile_error = True
        elif form.is_valid():
            report = form.save()
            _send_report_notification(report)
            submitted = True
            form = ContentReportForm()

    return render(request, "legal/report_content.html", {
        "form": form,
        "submitted": submitted,
        "turnstile_error": turnstile_error,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
        "rate_limited": False,
    })

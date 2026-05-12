import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import BadHeaderError
from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from config.email_utils import send_template_mail
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

    report_url = (
        f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}/messages/reports/{report.pk}/"
    )
    subject = f"[CulinEire] New content report: {report.get_report_type_display()}"
    try:
        send_template_mail(
            subject=subject,
            template="content_report",
            context={"report": report, "report_url": report_url},
            recipient_list=[notify_email],
            fail_silently=True,
        )
    except BadHeaderError:
        logger.warning("BadHeaderError sending report notification for report %s", report.pk)


def _create_report_message(report, sender):
    from messaging.models import Message
    from recipes.models import RecipeAuthor

    try:
        greenbear = RecipeAuthor.objects.select_related("user").get(slug="greenbear").user
    except RecipeAuthor.DoesNotExist:
        return None

    body_lines = [
        f"Type: {report.get_report_type_display()}",
    ]
    if report.reported_url:
        body_lines.append(f"URL: {report.reported_url}")
    body_lines.append(f"\n{report.description}")

    message = Message.objects.create(
        sender=sender,
        recipient=greenbear,
        subject=f"Content Report: {report.get_report_type_display()}",
        body="\n".join(body_lines),
    )
    return message


@login_required
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
            report = form.save(commit=False)
            report.reporter_user = request.user
            report.reporter_name = request.user.get_full_name() or request.user.username
            report.reporter_email = request.user.email
            report.save()
            message = _create_report_message(report, request.user)
            if message:
                report.linked_message = message
                report.save(update_fields=["linked_message"])
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

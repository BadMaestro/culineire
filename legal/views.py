import logging

from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.core.mail import BadHeaderError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import transaction
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from config.email_utils import build_absolute_url, send_template_mail
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


class TermsView(TemplateView):
    template_name = "legal/terms.html"


class CookiePolicyView(TemplateView):
    template_name = "legal/cookies.html"


class CompanyInformationView(TemplateView):
    template_name = "legal/company_information.html"


def _send_report_notification(report):
    notify_email = getattr(settings, "REPORT_NOTIFY_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
    if not notify_email:
        return

    report_url = build_absolute_url(reverse("legal:report_detail", args=[report.pk]))
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
        author = RecipeAuthor.objects.select_related("user").get(slug=settings.OWNER_SLUG)
        greenbear = author.user
    except RecipeAuthor.DoesNotExist:
        return None

    if not greenbear:
        return None

    body_lines = [
        f"Type: {report.get_report_type_display()}",
    ]
    if report.reported_url:
        body_lines.append(f"URL: {report.reported_url}")
    if report.evidence_url:
        body_lines.append(f"Evidence: {report.evidence_url}")
    if report.organisation:
        body_lines.append(f"Organisation: {report.organisation}")
    body_lines.append(f"\n{report.description}")

    message = Message.objects.create(
        sender=sender,
        recipient=greenbear,
        subject=f"Content Report: {report.get_report_type_display()}",
        body="\n".join(body_lines),
    )
    return message


@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def report_content(request):
    submitted = False
    turnstile_error = False

    # Pre-populate name/email for authenticated users
    initial_name = None
    initial_email = None
    if request.user.is_authenticated:
        initial_name = request.user.get_full_name() or request.user.username
        initial_email = request.user.email

    form = ContentReportForm(initial_name=initial_name, initial_email=initial_email)

    if request.method == "POST":
        if getattr(request, "limited", False):
            return render(request, "legal/report_content.html", {
                "form": form,
                "submitted": False,
                "turnstile_error": False,
                "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
                "rate_limited": True,
            })

        form = ContentReportForm(
            request.POST,
            initial_name=initial_name,
            initial_email=initial_email,
        )
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            turnstile_error = True
        elif form.is_valid():
            with transaction.atomic():
                report = form.save(commit=False)
                if request.user.is_authenticated:
                    report.reporter_user = request.user
                report.save()
                # Only create linked message if the reporter is authenticated
                if request.user.is_authenticated:
                    message = _create_report_message(report, request.user)
                    if message:
                        report.linked_message = message
                        report.save(update_fields=["linked_message"])
            _send_report_notification(report)
            submitted = True
            form = ContentReportForm(initial_name=initial_name, initial_email=initial_email)

    return render(request, "legal/report_content.html", {
        "form": form,
        "submitted": submitted,
        "turnstile_error": turnstile_error,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
        "rate_limited": False,
    })


# ── Reports admin ──────────────────────────────────────────────────────────────

@login_required
def reports_list(request):
    if not request.user.is_superuser:
        raise Http404
    from .models import ContentReport
    reports = (
        ContentReport.objects
        .select_related("reporter_user", "linked_message")
        .order_by("-created_at")
    )
    return render(request, "legal/reports_list.html", {"reports": reports})


@login_required
def report_detail(request, pk):
    if not request.user.is_superuser:
        raise Http404
    from .models import ContentReport
    report = get_object_or_404(
        ContentReport.objects.select_related("reporter_user", "linked_message"),
        pk=pk,
    )
    if request.method == "POST" and request.POST.get("action") == "resolve":
        note = request.POST.get("resolved_note", "").strip()
        report.is_resolved = True
        report.resolved_note = note
        report.save(update_fields=["is_resolved", "resolved_note"])
        django_messages.success(request, "Report marked as resolved.")
        return redirect("legal:reports_list")
    return render(request, "legal/report_detail.html", {"report": report})

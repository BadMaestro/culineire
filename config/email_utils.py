from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def sanitize_email_subject(subject: str, max_length: int = 200) -> str:
    """Strip newlines and control characters from email subject to prevent header injection."""
    return subject.replace("\r", "").replace("\n", "").strip()[:max_length]


def send_template_mail(subject, template, context, recipient_list, from_email=None, fail_silently=False):
    html_body = render_to_string(f"emails/{template}.html", context)
    text_body = render_to_string(f"emails/{template}.txt", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=fail_silently)

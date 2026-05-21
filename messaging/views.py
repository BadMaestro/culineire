import logging
from collections import defaultdict
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.core.mail import BadHeaderError
from config.email_utils import build_absolute_url, sanitize_email_subject, send_template_mail
from django.db import models, transaction
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django_ratelimit.decorators import ratelimit

from accounts.views import is_moderator
from .models import Message

logger = logging.getLogger(__name__)


def _moderation_redirect(request):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("recipes:moderation_panel")


@login_required
def inbox(request):
    user_involved = Message.objects.filter(
        models.Q(pk=OuterRef("pk")) | models.Q(parent=OuterRef("pk"))
    ).filter(
        models.Q(recipient=request.user) | models.Q(sender=request.user)
    )
    thread_roots = list(
        Message.objects.filter(parent=None, is_archived=False)
        .filter(Exists(user_involved))
        .select_related(
            "sender", "sender__recipe_author_profile",
            "recipient", "recipient__recipe_author_profile",
            "related_recipe", "related_article",
        )
    )

    replies_by_parent = defaultdict(list)
    if thread_roots:
        replies = (
            Message.objects.filter(parent_id__in=[message.pk for message in thread_roots])
            .select_related(
                "sender", "sender__recipe_author_profile",
                "recipient", "recipient__recipe_author_profile",
            )
            .order_by("created_at")
        )
        for reply in replies:
            replies_by_parent[reply.parent_id].append(reply)

    for root in thread_roots:
        thread = [root, *replies_by_parent.get(root.pk, [])]
        root.latest_message = max(thread, key=lambda message: message.created_at)
        root.has_unread = any(
            message.recipient_id == request.user.pk and not message.is_read
            for message in thread
        )

    user_messages = sorted(
        thread_roots,
        key=lambda message: message.latest_message.created_at,
        reverse=True,
    )

    return render(request, "messaging/inbox.html", {
        "user_messages": user_messages,
        "is_moderator": is_moderator(request.user),
    })


@login_required
def message_detail(request, pk):
    msg = get_object_or_404(
        Message.objects.select_related(
            "sender",
            "recipient",
            "parent",
            "related_recipe",
            "related_article",
        ),
        pk=pk,
    )
    root = msg.parent or msg
    thread_filter = models.Q(pk=root.pk) | models.Q(parent=root)

    if not Message.objects.filter(thread_filter).filter(
        models.Q(recipient=request.user) | models.Q(sender=request.user)
    ).exists():
        raise Http404

    Message.objects.filter(
        thread_filter,
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)

    thread = list(
        Message.objects.filter(thread_filter)
        .select_related("sender", "sender__recipe_author_profile", "recipient")
        .order_by("created_at")
    )
    if is_moderator(request.user):
        can_reply = thread[-1].sender_id != request.user.pk if thread else False
    else:
        can_reply = True

    return render(request, "messaging/message_detail.html", {
        "root_message": root,
        "thread": thread,
        "can_reply": can_reply,
    })


@require_POST
@login_required
def send_message(request):
    if not is_moderator(request.user):
        raise Http404

    from recipes.models import Recipe
    from articles.models import Article

    recipient_id = request.POST.get("recipient_id")
    body = request.POST.get("body", "").strip()
    subject = sanitize_email_subject(request.POST.get("subject", ""))
    recipe_id = request.POST.get("recipe_id")
    article_id = request.POST.get("article_id")
    action = request.POST.get("action", "message")

    if not body:
        django_messages.error(request, "Message body is required.")
        return _moderation_redirect(request)

    from django.contrib.auth import get_user_model
    user_model = get_user_model()
    recipe = None
    article = None
    if recipe_id:
        recipe = Recipe.objects.filter(pk=recipe_id).first()
    if article_id:
        article = Article.objects.filter(pk=article_id).first()

    if action == "reject_and_message" and bool(recipe) == bool(article):
        django_messages.error(request, "Choose exactly one item to reject and message about.")
        return _moderation_redirect(request)

    if action == "reject_and_message" and article:
        recipient = getattr(article.author, "user", None)
    elif action == "reject_and_message" and recipe:
        recipient = getattr(recipe.author, "user", None)
    elif recipient_id:
        recipient = get_object_or_404(user_model, pk=recipient_id)
    else:
        recipient = None

    if recipient is None:
        django_messages.error(request, "Message recipient is required.")
        return _moderation_redirect(request)

    if not subject:
        sender_profile = getattr(request.user, "recipe_author_profile", None)
        is_owner = sender_profile and sender_profile.slug == settings.OWNER_SLUG
        subject = (
            "Message from CulinEire Kitchen Head Chef"
            if is_owner
            else "Message from CulinEire Kitchen Sous Chef"
        )

    # Group into existing thread if no specific content context
    parent = None
    if not recipe and not article:
        existing = (
            Message.objects.filter(
                parent=None,
                is_archived=False,
            )
            .filter(
                models.Q(sender=request.user, recipient=recipient)
                | models.Q(sender=recipient, recipient=request.user)
            )
            .order_by("-created_at")
            .first()
        )
        if existing:
            parent = existing

    with transaction.atomic():
        Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=subject if not parent else "",
            body=body,
            parent=parent,
            related_recipe=recipe,
            related_article=article,
        )

        if action == "reject_and_message" and recipe:
            recipe.status = Recipe.Status.REJECTED
            recipe.moderation_note = body
            recipe.moderated_by = request.user
            recipe.moderated_at = timezone.now()
            recipe.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
            success_message = f'"{recipe.title}" rejected and author notified.'
        elif action == "reject_and_message" and article:
            article.status = Article.Status.REJECTED
            article.moderation_note = body
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
            success_message = f'"{article.title}" rejected and author notified.'
        else:
            success_message = "Message sent."

    try:
        send_template_mail(
            subject=subject,
            template="message_notification",
            context={
                "subject": subject,
                "body": body,
                "inbox_url": build_absolute_url(reverse("messaging:inbox")),
            },
            recipient_list=[recipient.email],
            fail_silently=True,
        )
    except (BadHeaderError, SMTPException):
        logger.warning("Failed to send message_notification email to %s", recipient.email)

    django_messages.success(request, success_message)

    return _moderation_redirect(request)


@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def contact(request):
    from django.conf import settings
    from config.turnstile import verify_turnstile
    from recipes.models import RecipeAuthor

    try:
        greenbear_user = RecipeAuthor.objects.select_related("user").get(slug=settings.OWNER_SLUG).user
    except RecipeAuthor.DoesNotExist:
        greenbear_user = None

    is_greenbear = (
        greenbear_user is not None
        and request.user.is_authenticated
        and request.user.pk == greenbear_user.pk
    )

    ctx_base = {
        "greenbear_available": greenbear_user is not None and not is_greenbear,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
        "is_greenbear": is_greenbear,
    }

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("login")

        if is_greenbear:
            return render(request, "messaging/contact.html", ctx_base)

        if getattr(request, "limited", False):
            return render(request, "messaging/contact.html", {
                **ctx_base,
                "error": "Too many messages. Please wait before trying again.",
            })

        # Honeypot — silent reject if bot fills hidden field
        if request.POST.get("website", "").strip():
            return redirect(request.path + "?sent=1")

        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            return render(request, "messaging/contact.html", {
                **ctx_base,
                "error": "Security check failed. Please try again.",
            })

        subject = sanitize_email_subject(request.POST.get("subject", ""))
        body = request.POST.get("body", "").strip()

        if not body:
            return render(request, "messaging/contact.html", {
                **ctx_base,
                "error": "Please enter a message.",
                "subject": subject,
            })

        from config.profanity import find_profanity as _find_profanity
        for _text in (subject, body):
            _bad = _find_profanity(_text)
            if _bad:
                _quoted = ", ".join(f'"{w}"' for w in _bad)
                return render(request, "messaging/contact.html", {
                    **ctx_base,
                    "error": f"Your message contains forbidden words: {_quoted}. Please remove them.",
                    "subject": subject,
                })

        if greenbear_user:
            existing = (
                Message.objects.filter(
                    parent=None,
                    is_archived=False,
                )
                .filter(
                    models.Q(sender=request.user, recipient=greenbear_user)
                    | models.Q(sender=greenbear_user, recipient=request.user)
                )
                .order_by("-created_at")
                .first()
            )
            parent = existing if existing else None
            Message.objects.create(
                sender=request.user,
                recipient=greenbear_user,
                subject=(subject or "Message from CulinEire Kitchen Author") if not parent else "",
                body=body,
                parent=parent,
            )
            return redirect(request.path + "?sent=1")

        django_messages.error(request, "Contact is unavailable right now. Please try again later.")
        return redirect("messaging:contact")

    # GET — check for ?sent=1 to show history state
    if request.GET.get("sent") == "1" and request.user.is_authenticated and greenbear_user:
        history = list(
            Message.objects.filter(
                sender=request.user,
                recipient=greenbear_user,
                parent=None,
            )
            .order_by("-created_at")
        )
        sender_profile = getattr(request.user, "recipe_author_profile", None)
        sender_name = (
            sender_profile.name if sender_profile
            else request.user.get_full_name() or request.user.username
        )
        return render(request, "messaging/contact.html", {
            **ctx_base,
            "sent": True,
            "sent_from": sender_name,
            "message_history": history,
        })

    return render(request, "messaging/contact.html", ctx_base)


@require_POST
@login_required
def reply_message(request, pk):
    msg = get_object_or_404(
        Message.objects.select_related("parent", "sender", "recipient"),
        pk=pk,
    )
    if msg.recipient != request.user and msg.sender != request.user:
        raise Http404
    parent = msg.parent or msg

    body = request.POST.get("body", "").strip()
    if not body:
        return redirect("messaging:message_detail", pk=pk)

    other = parent.sender if parent.recipient == request.user else parent.recipient

    reply = Message.objects.create(
        sender=request.user,
        recipient=other,
        subject=f"Re: {parent.subject}" if parent.subject else "",
        body=body,
        parent=parent,
        related_recipe=parent.related_recipe,
        related_article=parent.related_article,
    )

    try:
        send_template_mail(
            subject=reply.subject or "Reply from CulinEire",
            template="message_notification",
            context={
                "subject": reply.subject or "Reply from CulinEire",
                "body": body,
                "inbox_url": build_absolute_url(reverse("messaging:message_detail", args=[parent.pk])),
            },
            recipient_list=[other.email],
            fail_silently=True,
        )
    except (BadHeaderError, SMTPException):
        logger.warning("Failed to send reply notification email to %s", other.email)

    return redirect("messaging:message_detail", pk=parent.pk)


def _thread_root_for_user(pk, user):
    msg = get_object_or_404(
        Message.objects.select_related("sender", "recipient", "parent"),
        pk=pk,
    )
    root = msg.parent or msg
    thread_filter = models.Q(pk=root.pk) | models.Q(parent=root)
    if not Message.objects.filter(thread_filter).filter(
        models.Q(recipient=user) | models.Q(sender=user)
    ).exists():
        raise Http404
    return root


@require_POST
@login_required
def archive_message(request, pk):
    if not is_moderator(request.user):
        raise Http404
    root = _thread_root_for_user(pk, request.user)
    Message.objects.filter(
        models.Q(pk=root.pk) | models.Q(parent=root)
    ).update(is_archived=True, archived_at=timezone.now())
    django_messages.success(request, "Thread archived.")
    return redirect("messaging:inbox")


@require_POST
@login_required
def delete_message(request, pk):
    if not is_moderator(request.user):
        raise Http404
    root = _thread_root_for_user(pk, request.user)
    Message.objects.filter(
        models.Q(pk=root.pk) | models.Q(parent=root)
    ).delete()
    django_messages.success(request, "Thread deleted.")
    return redirect("messaging:inbox")


@require_POST
@login_required
def restore_message(request, pk):
    root = _thread_root_for_user(pk, request.user)
    Message.objects.filter(
        models.Q(pk=root.pk) | models.Q(parent=root)
    ).update(is_archived=False, archived_at=None)
    django_messages.success(request, "Thread restored.")
    return redirect("messaging:archive")


@login_required
def message_archive(request):
    user_involved = Message.objects.filter(
        models.Q(pk=OuterRef("pk")) | models.Q(parent=OuterRef("pk"))
    ).filter(
        models.Q(recipient=request.user) | models.Q(sender=request.user)
    )
    thread_roots = list(
        Message.objects.filter(parent=None, is_archived=True)
        .filter(Exists(user_involved))
        .select_related(
            "sender", "sender__recipe_author_profile",
            "recipient", "related_recipe", "related_article",
        )
        .order_by("-archived_at")
    )
    return render(request, "messaging/archive.html", {"archived_threads": thread_roots})

from collections import defaultdict

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from recipes.views import _is_moderator
from .models import Message


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
    thread_roots = list(
        Message.objects.filter(parent=None)
        .filter(
            models.Q(recipient=request.user)
            | models.Q(replies__recipient=request.user)
        )
        .select_related("sender", "recipient", "related_recipe", "related_article")
        .distinct()
    )

    replies_by_parent = defaultdict(list)
    if thread_roots:
        replies = (
            Message.objects.filter(parent_id__in=[message.pk for message in thread_roots])
            .select_related("sender", "recipient")
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

    return render(request, "messaging/inbox.html", {"user_messages": user_messages})


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
        .select_related("sender", "recipient")
        .order_by("created_at")
    )
    return render(request, "messaging/message_detail.html", {
        "root_message": root,
        "thread": thread,
    })


@require_POST
@login_required
def send_message(request):
    if not _is_moderator(request.user):
        raise Http404

    from recipes.models import Recipe
    from articles.models import Article

    recipient_id = request.POST.get("recipient_id")
    body = request.POST.get("body", "").strip()
    subject = request.POST.get("subject", "").strip()
    recipe_id = request.POST.get("recipe_id")
    article_id = request.POST.get("article_id")
    action = request.POST.get("action", "message")

    if not recipient_id or not body:
        django_messages.error(request, "Message body is required.")
        return _moderation_redirect(request)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    recipient = get_object_or_404(User, pk=recipient_id)

    recipe = None
    article = None
    if recipe_id:
        recipe = Recipe.objects.filter(pk=recipe_id).first()
    if article_id:
        article = Article.objects.filter(pk=article_id).first()

    Message.objects.create(
        sender=request.user,
        recipient=recipient,
        subject=subject,
        body=body,
        related_recipe=recipe,
        related_article=article,
    )

    try:
        send_mail(
            subject=subject or "Message from CulinEire moderation",
            message=body,
            from_email=None,
            recipient_list=[recipient.email],
            fail_silently=True,
        )
    except Exception:
        pass

    if action == "reject_and_message" and recipe:
        recipe.status = Recipe.Status.REJECTED if hasattr(Recipe.Status, "REJECTED") else "rejected"
        recipe.save(update_fields=["status"])
        django_messages.success(request, f'"{recipe.title}" rejected and author notified.')
    elif action == "reject_and_message" and article:
        article.status = Article.Status.REJECTED if hasattr(Article.Status, "REJECTED") else "rejected"
        article.save(update_fields=["status"])
        django_messages.success(request, f'"{article.title}" rejected and author notified.')
    else:
        django_messages.success(request, "Message sent.")

    return _moderation_redirect(request)


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
        send_mail(
            subject=reply.subject or "Reply from CulinEire",
            message=body,
            from_email=None,
            recipient_list=[other.email],
            fail_silently=True,
        )
    except Exception:
        pass

    return redirect("messaging:message_detail", pk=parent.pk)

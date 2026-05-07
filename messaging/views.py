from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from recipes.views import _is_moderator
from .models import Message


@login_required
def inbox(request):
    user_messages = Message.objects.filter(
        recipient=request.user, parent=None
    ).select_related("sender", "related_recipe", "related_article").order_by("-created_at")
    return render(request, "messaging/inbox.html", {"user_messages": user_messages})


@login_required
def message_detail(request, pk):
    msg = get_object_or_404(Message, pk=pk)
    if msg.recipient != request.user and msg.sender != request.user:
        raise Http404
    if msg.recipient == request.user and not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=["is_read"])
    thread = list(Message.objects.filter(
        models.Q(pk=msg.pk) | models.Q(parent=msg)
    ).select_related("sender", "recipient").order_by("created_at"))
    return render(request, "messaging/message_detail.html", {
        "root_message": msg,
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
        return redirect("recipes:moderation_panel")

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

    return redirect("recipes:moderation_panel")


@require_POST
@login_required
def reply_message(request, pk):
    parent = get_object_or_404(Message, pk=pk)
    if parent.recipient != request.user and parent.sender != request.user:
        raise Http404

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

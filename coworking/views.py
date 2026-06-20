from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import is_moderator

from .models import CoworkingAgent, CoworkingSharedMemory


def _require_access(request):
    if not is_moderator(request.user):
        raise Http404


def dashboard(request):
    _require_access(request)
    agents = CoworkingAgent.objects.prefetch_related("log_entries").all()
    shared = CoworkingSharedMemory.load()
    return render(request, "coworking/dashboard.html", {
        "agents": agents,
        "shared": shared,
        "other_agents_by_id": {a.agent_id: a for a in agents},
    })


@require_POST
def handoff(request):
    _require_access(request)
    from_id = request.POST.get("from_agent", "").strip()
    to_id = request.POST.get("to_agent", "").strip()
    note = request.POST.get("note", "").strip()

    if not from_id or not to_id or from_id == to_id:
        messages.error(request, "Choose two different agents to hand off between.")
        return redirect("coworking:dashboard")

    from_agent = get_object_or_404(CoworkingAgent, pk=from_id)
    to_agent = get_object_or_404(CoworkingAgent, pk=to_id)

    now = timezone.now()
    from_agent.status = CoworkingAgent.Status.IDLE
    from_agent.last_seen = now
    from_agent.save(update_fields=["status", "last_seen"])
    from_agent.log_entries.create(
        action=f"Handed off to {to_agent.label}",
        result="ok",
        note=note,
    )

    to_agent.status = CoworkingAgent.Status.ACTIVE
    to_agent.last_seen = now
    to_agent.save(update_fields=["status", "last_seen"])
    to_agent.log_entries.create(
        action=f"Received handoff from {from_agent.label}",
        result="ok",
        note=note,
    )

    messages.success(request, f"Handed off from {from_agent.label} to {to_agent.label}.")
    return redirect("coworking:dashboard")


@require_POST
def add_agent(request):
    _require_access(request)
    label = request.POST.get("label", "").strip()
    agent_id = request.POST.get("agent_id", "").strip()
    if not label:
        messages.error(request, "Label is required to add an agent.")
        return redirect("coworking:dashboard")
    if not agent_id:
        from django.utils.text import slugify
        agent_id = slugify(label)[:40]
    CoworkingAgent.objects.get_or_create(agent_id=agent_id, defaults={"label": label})
    messages.success(request, f"Registered agent: {label} ({agent_id}).")
    return redirect("coworking:dashboard")

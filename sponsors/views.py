import json

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import SponsorCell


# ---------------------------------------------------------------------------
# Public page
# ---------------------------------------------------------------------------

def puzzle_page(request):
    cells = SponsorCell.objects.all().order_by("ring", "position_in_ring")

    cells_data = [c.as_dict() for c in cells]

    sold = cells.filter(status=SponsorCell.Status.SOLD).count()
    reserved = cells.filter(status=SponsorCell.Status.RESERVED).count()
    available = cells.filter(status=SponsorCell.Status.AVAILABLE).count()
    # exclude centre from totals shown to visitors
    sellable_total = cells.exclude(ring=0).count()

    return render(
        request,
        "sponsors/puzzle.html",
        {
            "cells_data": cells_data,
            "sold": sold,
            "reserved": reserved,
            "available": available,
            "sellable_total": sellable_total,
            "percent_sold": round((sold / sellable_total * 100) if sellable_total else 0),
        },
    )


# ---------------------------------------------------------------------------
# AJAX: cell detail (GET)
# ---------------------------------------------------------------------------

@require_GET
def cell_detail(request, cell_id):
    cell = get_object_or_404(SponsorCell, pk=cell_id)
    data = cell.as_dict()

    if request.user.is_staff:
        data["is_admin"] = True
        data["enquiry_name"] = cell.enquiry_name
        data["enquiry_email"] = cell.enquiry_email
        data["enquiry_company"] = cell.enquiry_company
        data["enquiry_website"] = cell.enquiry_website
        data["enquiry_message"] = cell.enquiry_message
        data["enquiry_submitted_at"] = (
            cell.enquiry_submitted_at.isoformat()
            if cell.enquiry_submitted_at
            else None
        )
        data["logo_pending"] = cell.logo_pending.url if cell.logo_pending else None
        data["logo_offset_x"] = cell.logo_offset_x
        data["logo_offset_y"] = cell.logo_offset_y
        data["logo_scale"] = cell.logo_scale

    return JsonResponse(data)


# ---------------------------------------------------------------------------
# AJAX: submit enquiry (POST)
# ---------------------------------------------------------------------------

@require_POST
def cell_enquire(request, cell_id):
    cell = get_object_or_404(SponsorCell, pk=cell_id)

    if cell.status == SponsorCell.Status.SOLD:
        return JsonResponse({"error": "This spot is already sold."}, status=400)

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    company = request.POST.get("company", "").strip()
    website = request.POST.get("website", "").strip()
    message = request.POST.get("message", "").strip()

    if not name:
        return JsonResponse({"error": "Name is required."}, status=400)
    if not email:
        return JsonResponse({"error": "Email is required."}, status=400)

    cell.enquiry_name = name
    cell.enquiry_email = email
    cell.enquiry_company = company
    cell.enquiry_website = website
    cell.enquiry_message = message
    cell.enquiry_submitted_at = timezone.now()
    cell.status = SponsorCell.Status.RESERVED

    if "logo" in request.FILES:
        cell.logo_pending = request.FILES["logo"]
        try:
            cell.logo_offset_x = float(request.POST.get("offset_x", 0))
            cell.logo_offset_y = float(request.POST.get("offset_y", 0))
            cell.logo_scale = float(request.POST.get("scale", 1.0))
        except (ValueError, TypeError):
            cell.logo_offset_x = 0.0
            cell.logo_offset_y = 0.0
            cell.logo_scale = 1.0

    cell.save()

    # ---- Email notifications ----
    ring_label = "Central Founding Partner" if cell.ring == 0 else f"Ring {cell.ring}"
    subject = f"New Sponsor Enquiry — {ring_label} (Cell #{cell.cell_number})"

    body = (
        f"New sponsor enquiry received on CulinEire.\n\n"
        f"Ring: {ring_label}\n"
        f"Cell: #{cell.cell_number}\n"
        f"Price: {cell.price_display}\n\n"
        f"Name:    {name}\n"
        f"Email:   {email}\n"
        f"Company: {company or 'not provided'}\n"
        f"Website: {website or 'not provided'}\n\n"
        f"Message:\n{message or '(none)'}\n\n"
        f"{'Logo uploaded — review pending.' if 'logo' in request.FILES else 'No logo uploaded.'}\n\n"
        f"Review in admin:\nhttps://culineire.ie/cave19850324/sponsors/sponsorcell/{cell.pk}/change/\n"
    )

    # Notify Bearcave admin
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@culineire.ie"),
        recipient_list=["culineire@bearcave.ie"],
        fail_silently=True,
    )

    # Confirmation to the enquirer
    confirmation = (
        f"Hi {name},\n\n"
        f"Thank you for your interest in sponsoring CulinEire!\n\n"
        f"We have received your enquiry for the {ring_label} spot "
        f"(Cell #{cell.cell_number}, {cell.price_display}).\n\n"
        f"Bearcave Ltd. will contact you at {email} within 24 hours "
        f"to arrange the annual contract.\n\n"
        f"Best regards,\nThe CulinEire Team\nculineire@bearcave.ie\n"
    )

    send_mail(
        subject=f"Your CulinEire Sponsor Enquiry — {ring_label}",
        message=confirmation,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@culineire.ie"),
        recipient_list=[email],
        fail_silently=True,
    )

    return JsonResponse({"ok": True, "status": cell.status})


# ---------------------------------------------------------------------------
# AJAX: admin moderation (POST)
# ---------------------------------------------------------------------------

def _normalize_url(url):
    """Ensure URL has a protocol prefix."""
    if url and not url.lower().startswith(("http://", "https://")):
        return "https://" + url
    return url


@require_POST
def cell_moderate(request, cell_id):
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    cell = get_object_or_404(SponsorCell, pk=cell_id)
    action = request.POST.get("action", "")

    # approve: publish the cell as sold
    if action == "approve":
        if cell.logo_pending:
            cell.sponsor_logo = cell.logo_pending
            cell.logo_pending = None
        # Admin-supplied name takes priority; fall back to company, then personal name
        sponsor_name = request.POST.get("sponsor_name", "").strip()
        cell.sponsor_name = sponsor_name or cell.enquiry_company or cell.enquiry_name
        # Admin-supplied URL takes priority; fall back to enquiry website
        sponsor_url = _normalize_url(request.POST.get("sponsor_url", "").strip())
        cell.sponsor_url = sponsor_url or _normalize_url(cell.enquiry_website)
        cell.status = SponsorCell.Status.SOLD
        cell.purchased_at = timezone.now()
        cell.save()
        return JsonResponse({"ok": True, "status": "sold"})

    # edit: update sponsor info on an already-sold cell without changing status
    if action == "edit":
        sponsor_name = request.POST.get("sponsor_name", "").strip()
        if sponsor_name:
            cell.sponsor_name = sponsor_name
        sponsor_url = _normalize_url(request.POST.get("sponsor_url", "").strip())
        if sponsor_url:
            cell.sponsor_url = sponsor_url
        cell.save()
        return JsonResponse({"ok": True, "status": cell.status})

    # reject: clear enquiry and reset to available
    if action == "reject":
        if cell.logo_pending:
            cell.logo_pending.delete(save=False)
            cell.logo_pending = None
        cell.status = SponsorCell.Status.AVAILABLE
        cell.enquiry_name = ""
        cell.enquiry_email = ""
        cell.enquiry_company = ""
        cell.enquiry_website = ""
        cell.enquiry_message = ""
        cell.enquiry_submitted_at = None
        cell.save()
        return JsonResponse({"ok": True, "status": "available"})

    return JsonResponse({"error": "Invalid action."}, status=400)

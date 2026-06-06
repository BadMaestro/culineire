from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from recipes.validators import ImageUploadValidator

RING_PRICES = {0: 1000, 1: 800, 2: 400, 3: 200, 4: 100, 5: 50, 6: 25}

# Number of cells in each ring (outer to inner)
RING_CELL_COUNTS = {6: 60, 5: 50, 4: 40, 3: 30, 2: 20, 1: 10}


class SponsorCell(models.Model):
    class ProductType(models.TextChoices):
        ANNUAL_RING = "annual_ring", "Annual Ring Sponsorship"
        CENTRAL_MONTHLY = "central_monthly", "Central Sponsor of the Month"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        PAYMENT_PENDING = "payment_pending", "Payment pending"
        PAID_PENDING_APPROVAL = "paid_pending_approval", "Paid pending approval"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REJECTED = "rejected", "Rejected"
        UNAVAILABLE = "unavailable", "Unavailable"
        RESERVED = "reserved", "Reserved (legacy)"
        SOLD = "sold", "Sold (legacy)"

    # Cell identity
    cell_number = models.PositiveIntegerField(unique=True, db_index=True)
    ring = models.PositiveIntegerField(
        help_text="0 = centre (CulinEire logo), 1 = inner, 4 = outer",
        db_index=True,
    )
    position_in_ring = models.PositiveIntegerField(default=0)
    product_type = models.CharField(
        max_length=32,
        choices=ProductType.choices,
        default=ProductType.ANNUAL_RING,
        db_index=True,
    )

    # Status
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )

    # Sponsor info (populated only after approval/publication)
    sponsor_name = models.CharField(max_length=200, blank=True)
    sponsor_logo = models.ImageField(
        upload_to="sponsors/logos/",
        blank=True,
        null=True,
    )
    sponsor_url = models.URLField(blank=True)
    sponsor_tagline = models.CharField(max_length=200, blank=True)

    # Legacy pending logo/enquiry fields kept for compatibility with existing data.
    logo_pending = models.ImageField(
        upload_to="sponsors/pending/",
        blank=True,
        null=True,
    )
    logo_offset_x = models.FloatField(default=0.0)
    logo_offset_y = models.FloatField(default=0.0)
    logo_scale = models.FloatField(default=1.0)
    logo_rotation = models.FloatField(default=0.0)

    enquiry_name = models.CharField(max_length=200, blank=True)
    enquiry_email = models.EmailField(blank=True)
    enquiry_company = models.CharField(max_length=200, blank=True)
    enquiry_website = models.URLField(blank=True)
    enquiry_message = models.TextField(blank=True)
    enquiry_submitted_at = models.DateTimeField(null=True, blank=True)

    # Admin
    purchased_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ring", "position_in_ring"]
        verbose_name = "Sponsor Cell"
        verbose_name_plural = "Sponsor Cells"

    def __str__(self):
        if self.ring == 0:
            return "Centre (CulinEire)"
        label = self.sponsor_name or f"Cell #{self.cell_number}"
        return f"Ring {self.ring} / {label} [{self.get_status_display()}]"

    @property
    def price(self):
        return RING_PRICES.get(self.ring, 25)

    @property
    def price_net_cents(self):
        return int(self.price) * 100

    @property
    def price_display(self):
        if self.product_type == self.ProductType.CENTRAL_MONTHLY:
            return f"€{self.price:,}/month + VAT"
        return f"€{self.price:,}/year + VAT"

    @property
    def legacy_price_display(self):
        return f"€{self.price:,}/yr"

    @property
    def is_centre(self):
        return self.ring == 0

    @property
    def centre_label(self):
        return "Central Sponsor of the Month" if self.ring == 0 else None

    @property
    def is_public_active(self):
        return self.status in {self.Status.ACTIVE, self.Status.SOLD}

    @property
    def is_public_reserved(self):
        return self.status in {
            self.Status.PAYMENT_PENDING,
            self.Status.PAID_PENDING_APPROVAL,
            self.Status.RESERVED,
        }

    @property
    def is_available_for_checkout(self):
        return self.status == self.Status.AVAILABLE

    def as_dict(self):
        """Serialise to JSON-safe dict for the frontend puzzle renderer."""
        public_logo = self.sponsor_logo.url if self.sponsor_logo and self.is_public_active else None
        return {
            "id": self.pk,
            "cell_number": self.cell_number,
            "ring": self.ring,
            "position_in_ring": self.position_in_ring,
            "status": self.status,
            "sponsor_name": self.sponsor_name,
            "sponsor_logo": public_logo,
            "sponsor_url": self.sponsor_url if self.is_public_active else "",
            "sponsor_tagline": self.sponsor_tagline,
            "price": self.price,
            "price_net_cents": self.price_net_cents,
            "price_display": self.price_display,
            "is_centre": self.is_centre,
            "centre_label": self.centre_label,
            "logo_offset_x": self.logo_offset_x,
            "logo_offset_y": self.logo_offset_y,
            "logo_scale": self.logo_scale,
        }


class SponsorApplication(models.Model):
    TERMS_VERSION = "2026-06-06-compliance-v1"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PAYMENT_PENDING = "payment_pending", "Payment pending"
        PAID_PENDING_APPROVAL = "paid_pending_approval", "Paid pending approval"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REFUND_REQUIRED = "refund_required", "Refund required"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    cell = models.ForeignKey(
        SponsorCell,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    sponsor_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    website_url = models.URLField(blank=True)
    logo = models.ImageField(
        upload_to="sponsors/applications/",
        validators=[ImageUploadValidator(max_size=5 * 1024 * 1024)],
    )
    sponsor_note = models.TextField(blank=True)

    logo_offset_x = models.FloatField(default=0.0)
    logo_offset_y = models.FloatField(default=0.0)
    logo_scale = models.FloatField(default=1.0)
    logo_rotation = models.FloatField(default=0.0)

    price_net_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="eur")
    product_type = models.CharField(
        max_length=32,
        choices=SponsorCell.ProductType.choices,
        default=SponsorCell.ProductType.ANNUAL_RING,
        db_index=True,
    )
    term_days = models.PositiveIntegerField(default=365)

    logo_rights_confirmed = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    approval_acknowledged = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=80, default=TERMS_VERSION)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_sponsor_applications",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_sponsor_applications",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["cell", "status"]),
        ]

    def __str__(self):
        return f"{self.sponsor_name} / Cell #{self.cell.cell_number} [{self.get_status_display()}]"

    @property
    def price_net_euros(self):
        return self.price_net_cents / 100

    @property
    def price_display(self):
        amount = self.price_net_cents // 100
        if self.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY:
            return f"€{amount:,}/month + VAT"
        return f"€{amount:,}/year + VAT"

    @property
    def term_display(self):
        if self.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY:
            return "30-day term from approval/publication"
        return "12-month term from approval/publication"


class SanctionsEntry(models.Model):
    class Source(models.TextChoices):
        EU = "eu", "EU Consolidated Financial Sanctions List"
        UN = "un", "UN Security Council Consolidated List"
        MANUAL = "manual", "Manual compliance entry"

    source = models.CharField(max_length=16, choices=Source.choices, db_index=True)
    external_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255, db_index=True)
    aliases = models.JSONField(default=list, blank=True)
    country = models.CharField(max_length=100, blank=True)
    entity_type = models.CharField(max_length=50, blank=True)
    listed_on = models.DateField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="unique_sanctions_source_external_id"),
        ]

    def __str__(self):
        return f"{self.get_source_display()}: {self.name}"


class SponsorComplianceCheck(models.Model):
    class Status(models.TextChoices):
        NOT_CHECKED = "not_checked", "Not checked"
        CLEAR = "clear", "Compliance clear"
        POSSIBLE_MATCH = "possible_match", "Possible sanctions match"
        CONFIRMED_MATCH = "confirmed_match", "Confirmed sanctions match"
        FALSE_POSITIVE_CLEARED = "false_positive_cleared", "False positive cleared"
        BLOCKED = "blocked", "Blocked"
        ERROR = "error", "Screening error"

    application = models.ForeignKey(SponsorApplication, on_delete=models.CASCADE, related_name="compliance_checks")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NOT_CHECKED, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    source_summary = models.CharField(max_length=500, blank=True)
    matched_name = models.CharField(max_length=255, blank=True)
    matched_source = models.CharField(max_length=100, blank=True)
    match_score = models.FloatField(null=True, blank=True)
    checked_payload = models.JSONField(default=dict, blank=True)
    raw_matches = models.JSONField(default=list, blank=True)
    staff_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application.sponsor_name}: {self.get_status_display()}"


class SponsorPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"

    application = models.OneToOneField(
        SponsorApplication,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        unique=True,
        null=True,
    )
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    net_amount_cents = models.PositiveIntegerField(default=0)
    vat_amount_cents = models.PositiveIntegerField(default=0)
    total_amount_cents = models.PositiveIntegerField(default=0)
    refunded_amount_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="eur")
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["stripe_payment_intent_id"]),
        ]
        constraints = [
            # Issue 7: Enforce uniqueness for non-empty PaymentIntent IDs.
            models.UniqueConstraint(
                fields=["stripe_payment_intent_id"],
                condition=~models.Q(stripe_payment_intent_id=""),
                name="unique_nonempty_stripe_payment_intent_id",
            )
        ]

    def __str__(self):
        return f"{self.application.sponsor_name} payment [{self.get_status_display()}]"


class ProcessedStripeEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100, db_index=True)
    application = models.ForeignKey(
        SponsorApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stripe_events",
    )
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-processed_at"]

    def __str__(self):
        return f"{self.event_type} / {self.event_id}"


class SponsorAuditLog(models.Model):
    class Action(models.TextChoices):
        APPLICATION_CREATED = "application_created", "Application created"
        CHECKOUT_CREATED = "checkout_created", "Checkout created"
        CHECKOUT_FAILED = "checkout_failed", "Checkout failed"
        CHECKOUT_CANCELLED = "checkout_cancelled", "Checkout cancelled"
        CHECKOUT_EXPIRED = "checkout_expired", "Checkout expired"
        PAYMENT_CONFIRMED = "payment_confirmed", "Payment confirmed"
        PAYMENT_FAILED = "payment_failed", "Payment failed"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        READY_FOR_REVIEW = "ready_for_review", "Ready for review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REFUND_REQUIRED = "refund_required", "Refund required"
        REFUND_COMPLETED = "refund_completed", "Refund completed"
        UNPUBLISHED = "unpublished", "Unpublished"
        EXPIRED = "expired", "Expired"
        COMPLIANCE_CHECK_CLEAR = "compliance_check_clear", "Compliance check clear"
        COMPLIANCE_POSSIBLE_MATCH = "compliance_possible_match", "Compliance possible match"
        COMPLIANCE_BLOCKED = "compliance_blocked", "Compliance blocked"
        COMPLIANCE_FALSE_POSITIVE_CLEARED = "compliance_false_positive_cleared", "Compliance false positive cleared"
        COMPLIANCE_ERROR = "compliance_error", "Compliance error"

    application = models.ForeignKey(
        SponsorApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    cell = models.ForeignKey(
        SponsorCell,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sponsor_audit_logs",
    )
    action = models.CharField(max_length=64, choices=Action.choices, db_index=True)
    from_status = models.CharField(max_length=64, blank=True)
    to_status = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["application", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} at {self.created_at:%Y-%m-%d %H:%M}"


class SponsorRoadmapItem(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        READY_FOR_TEST = "ready_for_test", "Ready for test"
        DONE = "done", "Done"
        SKIPPED = "skipped", "Skipped"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    phase = models.CharField(max_length=100, default="Stripe Sponsors")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NOT_STARTED,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_blocker = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

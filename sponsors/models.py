from django.db import models

RING_PRICES = {0: 30000, 1: 800, 2: 400, 3: 200, 4: 100, 5: 50, 6: 25}

# Number of cells in each ring (outer to inner)
RING_CELL_COUNTS = {6: 60, 5: 50, 4: 40, 3: 30, 2: 20, 1: 10}


class SponsorCell(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"

    # Cell identity
    cell_number = models.PositiveIntegerField(unique=True, db_index=True)
    ring = models.PositiveIntegerField(
        help_text="0 = centre (CulinEire logo), 1 = inner, 4 = outer",
        db_index=True,
    )
    position_in_ring = models.PositiveIntegerField(default=0)

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )

    # Sponsor info (populated when sold/reserved)
    sponsor_name = models.CharField(max_length=200, blank=True)
    sponsor_logo = models.ImageField(
        upload_to="sponsors/logos/",
        blank=True,
        null=True,
    )
    sponsor_url = models.URLField(blank=True)
    sponsor_tagline = models.CharField(max_length=200, blank=True)

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
    def price_display(self):
        return f"€{self.price:,}/yr"

    @property
    def is_centre(self):
        return self.ring == 0

    @property
    def centre_label(self):
        return "Central Founding Partner" if self.ring == 0 else None

    def as_dict(self):
        """Serialise to JSON-safe dict for the frontend puzzle renderer."""
        return {
            "id": self.pk,
            "cell_number": self.cell_number,
            "ring": self.ring,
            "position_in_ring": self.position_in_ring,
            "status": self.status,
            "sponsor_name": self.sponsor_name,
            "sponsor_logo": self.sponsor_logo.url if self.sponsor_logo else None,
            "sponsor_url": self.sponsor_url,
            "sponsor_tagline": self.sponsor_tagline,
            "price": self.price,
            "price_display": self.price_display,
            "is_centre": self.is_centre,
            "centre_label": self.centre_label,
        }

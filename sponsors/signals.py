"""Keep sponsor logo files from orphaning on disk.

Every sponsor logo upload lands under MEDIA_ROOT with a collision-unique name, so
replacing a logo or deleting its row used to leave the old file behind. On
2026-07-28 that had accumulated 603 unreferenced files (35 MB) under
``sponsors/`` — logo duplicates plus test litter. These handlers remove a logo
file (and its generated ``.webp`` sibling) when its row is deleted or when the
field is replaced by a new upload, so the disk follows the database.

Wired in ``SponsorsConfig.ready``.
"""
from __future__ import annotations

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import SponsorApplication, SponsorCell

# model -> the FileField/ImageField names whose files we own.
_LOGO_FIELDS = {
    SponsorApplication: ("logo",),
    SponsorCell: ("sponsor_logo", "logo_pending"),
}

_WEBP_SOURCE_SUFFIXES = (".png", ".jpg", ".jpeg")


def _delete_file(fieldfile) -> None:
    """Delete a FieldFile's file and its ``.webp`` sibling, if present."""
    if not fieldfile:
        return
    name = fieldfile.name
    if not name:
        return
    storage = fieldfile.storage
    candidates = [name]
    for suffix in _WEBP_SOURCE_SUFFIXES:
        if name.lower().endswith(suffix):
            candidates.append(name[: -len(suffix)] + ".webp")
            break
    for candidate in candidates:
        # storage.delete is a no-op if the file is already gone, but exists()
        # first avoids a needless remote call and keeps errors quiet.
        if storage.exists(candidate):
            storage.delete(candidate)


@receiver(post_delete, sender=SponsorApplication)
@receiver(post_delete, sender=SponsorCell)
def _remove_logo_files_on_delete(sender, instance, **kwargs):
    for field in _LOGO_FIELDS[sender]:
        _delete_file(getattr(instance, field, None))


@receiver(pre_save, sender=SponsorApplication)
@receiver(pre_save, sender=SponsorCell)
def _remove_replaced_logo_files(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    for field in _LOGO_FIELDS[sender]:
        old_file = getattr(old, field, None)
        new_file = getattr(instance, field, None)
        old_name = old_file.name if old_file else ""
        new_name = new_file.name if new_file else ""
        if old_name and old_name != new_name:
            _delete_file(old_file)

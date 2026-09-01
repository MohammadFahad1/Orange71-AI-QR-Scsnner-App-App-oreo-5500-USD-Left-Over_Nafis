import io
import uuid

import qrcode
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AmbassadorBooking


def generate_qr_image(data: str) -> ContentFile:
    """Generate a QR code PNG for the given string and return it as a ContentFile."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue())


@receiver(post_save, sender='authentication.AmbassadorBooking')
def generate_brand_qr(sender, instance, created, **kwargs):
    """
    Fires when an AmbassadorBooking is saved.
    If the booking is completed, has an ambassador_link, and no brand_qr yet:
    - Generates a QR code PNG that encodes the ambassador_link.
    - Saves it to the booking's brand_qr field without triggering another post_save.
    """
    if instance.completed_at is None or not instance.ambassador_link or instance.brand_qr:
        return

    image_content = generate_qr_image(instance.ambassador_link)
    filename = f'ambassador_brand_qr_{instance.pk}.png'
    instance.brand_qr.save(filename, image_content, save=False)
    sender.objects.filter(pk=instance.pk).update(brand_qr=instance.brand_qr.name)


@receiver(post_save, sender='authentication.User')
def assign_slug_and_qr(sender, instance, created, **kwargs):
    """
    Fires once when a new User is created.
    - Generates a unique UUID slug as the user's permanent identity.
    - Generates a QR code PNG that encodes the slug.
      The mobile app scans this QR, reads the slug, and calls
      POST /api/chat/scan/<slug>/ to initiate a connection.
    """
    if not created:
        return

    update_fields = {}

    if not instance.slug:
        update_fields['slug'] = str(uuid.uuid4())
        instance.slug = update_fields['slug']

    if not instance.qr_code:
        slug = instance.slug or update_fields.get('slug')
        image_content = generate_qr_image(slug)
        # Save the file to storage without triggering another post_save
        instance.qr_code.save(f'{slug}.png', image_content, save=False)
        update_fields['qr_code'] = instance.qr_code.name

    if update_fields:
        # Use queryset update to avoid re-triggering the signal
        sender.objects.filter(pk=instance.pk).update(**update_fields)

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from authentication.signals import generate_qr_image

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate slugs and QR codes for existing users who are missing them.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many users would be updated without making changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        users = User.objects.filter(slug__isnull=True) | User.objects.filter(qr_code='')
        # Deduplicate (union can produce duplicates)
        users = User.objects.filter(
            pk__in=users.values('pk')
        ).order_by('id')

        total = users.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('All users already have slugs and QR codes. Nothing to do.'))
            return

        if dry_run:
            self.stdout.write(f'Dry run: {total} user(s) would be updated.')
            return

        updated = 0
        errors = 0

        for user in users:
            try:
                update_fields = {}

                if not user.slug:
                    user.slug = str(uuid.uuid4())
                    update_fields['slug'] = user.slug

                if not user.qr_code:
                    slug = user.slug
                    image_content = generate_qr_image(slug)
                    user.qr_code.save(f'{slug}.png', image_content, save=False)
                    update_fields['qr_code'] = user.qr_code.name

                if update_fields:
                    User.objects.filter(pk=user.pk).update(**update_fields)
                    updated += 1
                    self.stdout.write(f'  ✓ {user.email}')

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  ✗ {user.email}: {e}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Done. {updated} updated, {errors} failed.'))

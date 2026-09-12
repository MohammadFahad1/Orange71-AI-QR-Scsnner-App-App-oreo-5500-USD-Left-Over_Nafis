import uuid

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
	use_in_migrations = True

	def create_user(self, email, name, password=None, **extra_fields):
		if not email:
			raise ValueError('The Email field must be set.')
		if not name:
			raise ValueError('The Name field must be set.')

		email = self.normalize_email(email)
		user = self.model(email=email, name=name, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, name, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('is_active', True)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return self.create_user(email=email, name=name, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	
    ACCOUNT_TYPE_CHOICES = (
        ('member', 'Member'),
		('VIP', 'VIP'),
		('Ambassador', 'Ambassador'),
		('fundraiser', 'Fundraiser'),
    )
	
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    profile_picture = models.URLField(blank=True, null=True)
    profile_picture_local = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    nickname = models.CharField(max_length=150, blank=True, null=True)
    otp = models.CharField(max_length=4, blank=True, null=True)
    otp_generated_at = models.DateTimeField(blank=True, null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='member')
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email


class SpeacialEvent(models.Model):
	special_event = models.URLField()

	def save(self, *args, **kwargs):
		self.pk = 1
		if SpeacialEvent.objects.exclude(pk=self.pk).exists():
			raise ValueError('Only one SpeacialEvent instance is allowed.')
		return super().save(*args, **kwargs)

	def __str__(self):
		return self.special_event


class AmbassadorSlot(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError('start_time must be earlier than end_time.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.start_time} - {self.end_time}'


class AmbassadorBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ambassador_bookings')
    slot = models.OneToOneField(AmbassadorSlot, on_delete=models.PROTECT, related_name='booking')
    ambassador_link = models.URLField(blank=True, null=True)
    brand_qr = models.ImageField(upload_to='ambassador_qr_codes/', blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_ambassador_booking_per_user'),
        ]

    def __str__(self):
        return f'{self.user.email} -> {self.slot}'


class Support(models.Model):
	full_name = models.CharField(max_length=150)
	email = models.EmailField()
	how_can_i_help_you = models.TextField(verbose_name='How can I help you?')
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f'{self.full_name} <{self.email}>'


class RingExchangePolicy(models.Model):
    CHARGE_TYPE_FIXED = "fixed"
    CHARGE_TYPE_PERCENTAGE = "percentage"
    CHARGE_TYPE_SHIPPING_ONLY = "shipping_only"
    CHARGE_TYPE_CHOICES = [
        (CHARGE_TYPE_FIXED, "Fixed Amount"),
        (CHARGE_TYPE_PERCENTAGE, "Percentage of Ring Cost"),
        (CHARGE_TYPE_SHIPPING_ONLY, "Shipping Cost Only"),
    ]

    free_exchange_days = models.PositiveIntegerField(
        default=14,
        help_text="Number of days from purchase date during which exchanges are free (if ring is not broken).",
    )
    charge_type = models.CharField(
        max_length=20,
        choices=CHARGE_TYPE_CHOICES,
        default=CHARGE_TYPE_SHIPPING_ONLY,
        help_text="How fee is calculated after free exchange window or if ring is broken.",
    )
    fixed_fee_amount = models.PositiveIntegerField(
        default=0,
        help_text="Fixed exchange fee amount in cents (e.g. 1500 = $15.00). Used when charge_type='fixed'.",
    )
    fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentage of ring cost (e.g. 20.00 = 20%). Used when charge_type='percentage'.",
    )
    shipping_cost = models.PositiveIntegerField(
        default=500,
        help_text="Flat shipping fee in cents (e.g. 500 = $5.00). Added to fee or used when charge_type='shipping_only'.",
    )
    currency = models.CharField(max_length=10, default="usd")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ring Exchange Policy"
        verbose_name_plural = "Ring Exchange Policy"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_policy(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Exchange Policy ({self.free_exchange_days} free days, type: {self.charge_type})"


class RingExchangeRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAYMENT_PENDING = "payment_pending"
    STATUS_APPROVED = "approved"
    STATUS_USER_SHIPPED = "user_shipped"
    STATUS_RING_RECEIVED = "ring_received"
    STATUS_REPLACEMENT_SHIPPED = "replacement_shipped"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAYMENT_PENDING, "Payment Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_USER_SHIPPED, "Original Ring Shipped by User"),
        (STATUS_RING_RECEIVED, "Original Ring Received by Company"),
        (STATUS_REPLACEMENT_SHIPPED, "Replacement Ring Shipped"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    PAYMENT_NOT_REQUIRED = "not_required"
    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_NOT_REQUIRED, "Not Required"),
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ring_exchanges",
    )
    order_id = models.CharField(max_length=100)
    original_item_name = models.CharField(max_length=255)
    original_size = models.CharField(max_length=50)
    desired_size = models.CharField(max_length=50)
    is_damaged = models.BooleanField(
        default=False,
        help_text="Check if the ring is broken or damaged.",
    )
    purchase_date = models.DateTimeField()
    original_price = models.PositiveIntegerField(
        default=0,
        help_text="Original item price in smallest currency unit (e.g. cents).",
    )
    calculated_fee = models.PositiveIntegerField(
        default=0,
        help_text="Calculated exchange fee in cents.",
    )
    shipping_cost = models.PositiveIntegerField(
        default=0,
        help_text="Shipping cost portion in cents.",
    )
    total_amount = models.PositiveIntegerField(
        default=0,
        help_text="Total charge (fee + shipping) in cents.",
    )
    currency = models.CharField(max_length=10, default="usd")
    is_within_free_window = models.BooleanField(default=True)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_NOT_REQUIRED,
    )
    stripe_session_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255, blank=True, null=True
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    user_tracking_number = models.CharField(
        max_length=100, blank=True, null=True
    )
    replacement_tracking_number = models.CharField(
        max_length=100, blank=True, null=True
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def calculate_exchange_fee(cls, policy, purchase_date, is_damaged, original_price_cents):
        from django.utils import timezone
        now = timezone.now()
        days_passed = (now - purchase_date).days if purchase_date else 0
        within_free_window = days_passed <= policy.free_exchange_days

        is_free = within_free_window and (not is_damaged)

        if is_free:
            return {
                "is_free": True,
                "within_free_window": True,
                "fee": 0,
                "shipping": 0,
                "total": 0,
            }

        fee = 0
        if policy.charge_type == RingExchangePolicy.CHARGE_TYPE_FIXED:
            fee = policy.fixed_fee_amount
        elif policy.charge_type == RingExchangePolicy.CHARGE_TYPE_PERCENTAGE:
            fee = int(original_price_cents * (float(policy.fee_percentage) / 100.0))
        elif policy.charge_type == RingExchangePolicy.CHARGE_TYPE_SHIPPING_ONLY:
            fee = 0

        shipping = policy.shipping_cost
        total = fee + shipping

        return {
            "is_free": total == 0,
            "within_free_window": within_free_window,
            "fee": fee,
            "shipping": shipping,
            "total": total,
        }

    def __str__(self):
        return f"RingExchangeRequest({self.user.email} - Order #{self.order_id})"


class RefundPolicy(models.Model):
    refund_deadline_days = models.PositiveIntegerField(
        default=21,
        help_text="Number of days from purchase date during which a refund can be requested (default: 21 days).",
    )
    return_shipping_address = models.TextField(
        default="Amore Rings Returns Dept.\n123 Luxury Lane, Suite 100\nNew York, NY 10001, USA",
        help_text="Address where customers should mail returned rings.",
    )
    instructions = models.TextField(
        default="To return your ring for a refund, please package the item securely in its original box and ship it to our returns department. Attach your shipment tracking number to this request once mailed.",
        help_text="Instructions displayed to customers when requesting a refund.",
    )
    restocking_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Optional restocking fee percentage (e.g. 0.00 for no fee).",
    )
    currency = models.CharField(max_length=10, default="usd")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Refund Policy"
        verbose_name_plural = "Refund Policy"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_policy(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Refund Policy ({self.refund_deadline_days} days deadline)"


class RefundRequest(models.Model):
    STATUS_REQUESTED = "requested"
    STATUS_RING_SHIPPED = "ring_shipped"
    STATUS_RING_RECEIVED = "ring_received"
    STATUS_REFUND_PROCESSED = "refund_processed"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_RING_SHIPPED, "Ring Shipped by User"),
        (STATUS_RING_RECEIVED, "Ring Received by Company"),
        (STATUS_REFUND_PROCESSED, "Refund Processed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )
    order_id = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    item_size = models.CharField(max_length=50, blank=True, null=True)
    reason = models.TextField()
    purchase_date = models.DateTimeField()
    original_price = models.FloatField(
        default=0,
        help_text="Original item purchase price in smallest currency unit (e.g. cents).",
    )
    refund_amount = models.FloatField(
        default=0,
        help_text="Eligible refund amount in cents.",
    )
    currency = models.CharField(max_length=10, default="usd")
    return_deadline = models.DateTimeField()
    is_eligible = models.BooleanField(
        default=True,
        help_text="True if request was submitted within the refund deadline window.",
    )
    user_tracking_number = models.CharField(
        max_length=100, blank=True, null=True
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_REQUESTED
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def calculate_refund(cls, policy, purchase_date, original_price_cents):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        deadline = purchase_date + timedelta(days=policy.refund_deadline_days)
        is_eligible = now <= deadline

        restocking_fee = int(original_price_cents * (float(policy.restocking_fee_percentage) / 100.0))
        refund_amount = max(0, original_price_cents - restocking_fee)

        return {
            "is_eligible": is_eligible,
            "return_deadline": deadline,
            "original_price": original_price_cents,
            "restocking_fee": restocking_fee,
            "refund_amount": refund_amount,
        }

    def __str__(self):
        return f"RefundRequest({self.user.email} - Order #{self.order_id})"



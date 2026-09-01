import uuid

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

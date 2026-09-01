from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import (
    AmbassadorBooking,
    AmbassadorSlot,
    SpeacialEvent,
    Support,
    User,
    RingExchangePolicy,
    RingExchangeRequest,
)


class AmbassadorBookingInline(admin.TabularInline):
    model = AmbassadorBooking
    max_num = 1
    can_delete = False
    extra = 0
    readonly_fields = ['slot', 'brand_qr', 'completed_at', 'created_at']
    fields = ['slot', 'ambassador_link', 'brand_qr', 'completed_at', 'created_at']


@admin.register(AmbassadorSlot)
class AmbassadorSlotAdmin(admin.ModelAdmin):
    list_display = ('start_time', 'end_time', 'is_available')
    ordering = ('start_time',)


@admin.register(AmbassadorBooking)
class AmbassadorBookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'slot', 'completed_at', 'ambassador_link')
    list_filter = ('completed_at',)
    list_editable = ('ambassador_link',)
    ordering = ('-created_at',)
    actions = ['mark_as_completed']

    def mark_as_completed(self, request, queryset):
        for booking in queryset:
            booking.completed_at = timezone.now()
            booking.save(update_fields=['completed_at'])
    mark_as_completed.short_description = 'Mark selected bookings as completed'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [AmbassadorBookingInline]
    model = User
    list_display = ('email', 'name', 'is_staff', 'is_active','otp')
    list_filter = ('is_staff', 'is_active', 'groups')
    search_fields = ('email', 'name')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'name', 'password')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'name', 'password1', 'password2', 'is_staff', 'is_active'),
            },
        ),
    )


@admin.register(SpeacialEvent)
class SpeacialEventAdmin(admin.ModelAdmin):
	list_display = ('special_event',)

	def has_add_permission(self, request):
		if SpeacialEvent.objects.exists():
			return False
		return super().has_add_permission(request)


@admin.register(Support)
class SupportAdmin(admin.ModelAdmin):
	list_display = ('full_name', 'email', 'created_at')
	search_fields = ('full_name', 'email', 'how_can_i_help_you')
	ordering = ('-created_at',)


@admin.register(RingExchangePolicy)
class RingExchangePolicyAdmin(admin.ModelAdmin):
    list_display = (
        'free_exchange_days',
        'charge_type',
        'fixed_fee_amount',
        'fee_percentage',
        'shipping_cost',
        'currency',
        'updated_at',
    )

    def has_add_permission(self, request):
        if RingExchangePolicy.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(RingExchangeRequest)
class RingExchangeRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'order_id',
        'original_item_name',
        'original_size',
        'desired_size',
        'is_damaged',
        'is_within_free_window',
        'calculated_fee',
        'shipping_cost',
        'total_amount',
        'payment_status',
        'status',
        'user_tracking_number',
        'replacement_tracking_number',
        'created_at',
    )
    list_filter = ('status', 'payment_status', 'is_damaged', 'is_within_free_window', 'created_at')
    search_fields = ('user__email', 'order_id', 'original_item_name', 'user_tracking_number', 'replacement_tracking_number')
    list_editable = ('status', 'replacement_tracking_number')
    ordering = ('-created_at',)


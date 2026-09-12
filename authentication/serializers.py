import datetime
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    AmbassadorBooking,
    AmbassadorSlot,
    Support,
    RingExchangePolicy,
    RingExchangeRequest,
    RefundPolicy,
    RefundRequest,
)


User = get_user_model()



class AmbassadorSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmbassadorSlot
        fields = ('id', 'start_time', 'end_time', 'is_available', 'created_at')


class AmbassadorBookSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()


class AmbassadorBookingSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    slot = AmbassadorSlotSerializer(read_only=True)
    brand_qr = serializers.SerializerMethodField()

    class Meta:
        model = AmbassadorBooking
        fields = ('id', 'user', 'slot', 'completed_at', 'ambassador_link', 'brand_qr', 'created_at')

    def get_brand_qr(self, obj):
        if not obj.brand_qr:
            return None
        request = self.context.get('request') if hasattr(self, 'context') and self.context else None
        url = obj.brand_qr.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class SpeacialEventSerializer(serializers.Serializer):
    special_event = serializers.URLField()


class UserSerializer(serializers.ModelSerializer):
    profile_picture_local = serializers.SerializerMethodField()
    qr_code = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'name', 'email', 'slug', 'nickname', 'website', 'profile_picture', 'profile_picture_local', 'qr_code')

    def get_profile_picture_local(self, obj) -> str:
        if not obj.profile_picture_local:
            return None
        url = obj.profile_picture_local.url
        request = self.context.get('request') if hasattr(self, 'context') else None
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_qr_code(self, obj) -> str:
        if not obj.qr_code:
            return None
        request = self.context.get('request') if hasattr(self, 'context') else None
        url = obj.qr_code.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url




class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=4)


class OtpSentSerializer(serializers.Serializer):
    detail = serializers.CharField()
    email = serializers.EmailField()


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    user = UserSerializer()
    refresh = serializers.CharField()
    access = serializers.CharField()


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField()


class SupportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Support
        fields = ('full_name', 'email', 'how_can_i_help_you')


class UserUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=False, allow_null=False)
    profile_picture_local = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('At least one field must be provided.')
        return attrs


class RingExchangePolicySerializer(serializers.ModelSerializer):
    user_purchase_date = serializers.SerializerMethodField()
    user_free_exchange_deadline = serializers.SerializerMethodField()
    free_exchange_deadline_date = serializers.SerializerMethodField()
    exchange_deadline_date = serializers.SerializerMethodField()
    is_within_free_window = serializers.SerializerMethodField()

    class Meta:
        model = RingExchangePolicy
        fields = (
            'free_exchange_days',
            'charge_type',
            'fixed_fee_amount',
            'fee_percentage',
            'shipping_cost',
            'currency',
            'updated_at',
            'user_purchase_date',
            'user_free_exchange_deadline',
            'free_exchange_deadline_date',
            'exchange_deadline_date',
            'is_within_free_window',
        )

    def _get_user_purchase_info(self, obj):
        if not hasattr(self, '_cached_purchase_info'):
            request = self.context.get('request')
            if request and getattr(request, 'user', None) and request.user.is_authenticated:
                from .views import get_user_ring_purchase_date
                order_id = request.query_params.get('order_id') if hasattr(request, 'query_params') else None
                self._cached_purchase_info = get_user_ring_purchase_date(request.user, order_id=order_id)
            else:
                self._cached_purchase_info = None
        return self._cached_purchase_info

    def get_user_purchase_date(self, obj):
        purchase_date = self._get_user_purchase_info(obj)
        return purchase_date.isoformat() if purchase_date else None

    def get_user_free_exchange_deadline(self, obj):
        purchase_date = self._get_user_purchase_info(obj)
        if purchase_date:
            if timezone.is_naive(purchase_date):
                purchase_date = timezone.make_aware(purchase_date, timezone.get_current_timezone())
            deadline = purchase_date + datetime.timedelta(days=obj.free_exchange_days)
            return deadline.isoformat()
        return None

    def get_free_exchange_deadline_date(self, obj):
        return self.get_user_free_exchange_deadline(obj)

    def get_exchange_deadline_date(self, obj):
        return self.get_user_free_exchange_deadline(obj)

    def get_is_within_free_window(self, obj):
        purchase_date = self._get_user_purchase_info(obj)
        if purchase_date:
            if timezone.is_naive(purchase_date):
                purchase_date = timezone.make_aware(purchase_date, timezone.get_current_timezone())
            deadline = purchase_date + datetime.timedelta(days=obj.free_exchange_days)
            now = timezone.now()
            if timezone.is_naive(deadline):
                deadline = timezone.make_aware(deadline, timezone.get_current_timezone())
            return now <= deadline
        return None


class RingExchangeRequestCreateSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=100)
    original_item_name = serializers.CharField(max_length=255)
    original_size = serializers.CharField(max_length=50)
    desired_size = serializers.CharField(max_length=50)
    is_damaged = serializers.BooleanField(default=False)
    purchase_date = serializers.DateTimeField(required=False, allow_null=True)
    original_price = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Original item price. Optional if WooCommerce is connected.",
    )
    success_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)


class RingExchangeRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RingExchangeRequest
        fields = (
            'id',
            'order_id',
            'original_item_name',
            'original_size',
            'desired_size',
            'is_damaged',
            'purchase_date',
            'original_price',
            'calculated_fee',
            'shipping_cost',
            'total_amount',
            'currency',
            'is_within_free_window',
            'payment_status',
            'stripe_session_id',
            'status',
            'user_tracking_number',
            'replacement_tracking_number',
            'notes',
            'created_at',
            'updated_at',
        )


class RingExchangeTrackingUpdateSerializer(serializers.Serializer):
    user_tracking_number = serializers.CharField(max_length=100)


class RefundPolicySerializer(serializers.ModelSerializer):
    user_purchase_date = serializers.SerializerMethodField()
    user_refund_deadline = serializers.SerializerMethodField()
    refund_deadline_date = serializers.SerializerMethodField()
    return_deadline = serializers.SerializerMethodField()
    is_eligible = serializers.SerializerMethodField()

    class Meta:
        model = RefundPolicy
        fields = (
            'refund_deadline_days',
            'return_shipping_address',
            'instructions',
            'restocking_fee_percentage',
            'currency',
            'updated_at',
            'user_purchase_date',
            'user_refund_deadline',
            'refund_deadline_date',
            'return_deadline',
            'is_eligible',
        )

    def _get_user_purchase_info(self, obj):
        if not hasattr(self, '_cached_purchase_info'):
            request = self.context.get('request')
            if request and getattr(request, 'user', None) and request.user.is_authenticated:
                from .views import get_user_ring_purchase_date
                order_id = request.query_params.get('order_id') if hasattr(request, 'query_params') else None
                self._cached_purchase_info = get_user_ring_purchase_date(request.user, order_id=order_id)
            else:
                self._cached_purchase_info = None
        return self._cached_purchase_info

    def get_user_purchase_date(self, obj):
        purchase_date = self._get_user_purchase_info(obj)
        return purchase_date.isoformat() if purchase_date else None

    def get_user_refund_deadline(self, obj):
        purchase_date = self._get_user_purchase_info(obj)
        if purchase_date:
            deadline = purchase_date + datetime.timedelta(days=obj.refund_deadline_days)
            return deadline.isoformat()
        return None

    def get_refund_deadline_date(self, obj):
        return self.get_user_refund_deadline(obj)

    def get_return_deadline(self, obj):
        return self.get_user_refund_deadline(obj)

    def get_is_eligible(self, obj):
        purchase_date = self._get_user_purchase_info(obj)
        if purchase_date:
            if timezone.is_naive(purchase_date):
                purchase_date = timezone.make_aware(purchase_date, timezone.get_current_timezone())
            deadline = purchase_date + datetime.timedelta(days=obj.refund_deadline_days)
            now = timezone.now()
            if timezone.is_naive(deadline):
                deadline = timezone.make_aware(deadline, timezone.get_current_timezone())
            return now <= deadline
        return None


class RefundRequestCreateSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=100)
    item_name = serializers.CharField(max_length=255)
    item_size = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    reason = serializers.CharField()
    purchase_date = serializers.DateTimeField(required=False, allow_null=True)
    original_price = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Original purchase price. Optional if WooCommerce is connected.",
    )


class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = (
            'id',
            'order_id',
            'item_name',
            'item_size',
            'reason',
            'purchase_date',
            'original_price',
            'refund_amount',
            'currency',
            'return_deadline',
            'is_eligible',
            'user_tracking_number',
            'status',
            'notes',
            'created_at',
            'updated_at',
        )


class RefundTrackingUpdateSerializer(serializers.Serializer):
    user_tracking_number = serializers.CharField(max_length=100)



from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    AmbassadorBooking,
    AmbassadorSlot,
    Support,
    RingExchangePolicy,
    RingExchangeRequest,
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
        )


class RingExchangeRequestCreateSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=100)
    original_item_name = serializers.CharField(max_length=255)
    original_size = serializers.CharField(max_length=50)
    desired_size = serializers.CharField(max_length=50)
    is_damaged = serializers.BooleanField(default=False)
    purchase_date = serializers.DateTimeField(required=False, allow_null=True)
    original_price = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Original item price in smallest currency unit (e.g. cents). Optional if WooCommerce is connected.",
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


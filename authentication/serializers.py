from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AmbassadorBooking, AmbassadorSlot, Support


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

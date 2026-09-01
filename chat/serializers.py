from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Conversation, Message, CreditBalance, Block, UserConnection, CreditPackage, CreditPurchase

User = get_user_model()


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'name', 'email', 'profile_picture', 'profile_picture_local')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.profile_picture_local and request:
            data['profile_picture_local'] = request.build_absolute_uri(
                instance.profile_picture_local.url
            )
        return data


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    sender_name = serializers.CharField(source='sender.name', read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender_id', 'sender_name', 'content', 'created_at')
        read_only_fields = ('id', 'conversation', 'sender_id', 'sender_name', 'created_at')


class ConversationSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_blocked_by_me = serializers.SerializerMethodField()
    is_blocked_by_them = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            'id', 'participants', 'last_message', 'unread_count',
            'is_blocked_by_me', 'is_blocked_by_them', 'created_at',
        )

    def _other_participant(self, obj):
        """Return the participant who is not the requesting user, or None."""
        request = self.context.get('request')
        if request is None:
            return None
        return obj.participants.exclude(id=request.user.id).first()

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if msg is None:
            return None
        return {
            'id': msg.id,
            'sender_id': msg.sender_id,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
        }

    def get_unread_count(self, obj):
        # Placeholder — implement read receipts in a future iteration
        return 0

    def get_is_blocked_by_me(self, obj):
        request = self.context.get('request')
        if request is None:
            return False
        other = self._other_participant(obj)
        if other is None:
            return False
        return Block.objects.filter(blocker=request.user, blocked=other).exists()

    def get_is_blocked_by_them(self, obj):
        request = self.context.get('request')
        if request is None:
            return False
        other = self._other_participant(obj)
        if other is None:
            return False
        return Block.objects.filter(blocker=other, blocked=request.user).exists()


class CreditBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditBalance
        fields = ('balance', 'updated_at')


class CreditPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPackage
        fields = ('id', 'name', 'credits_amount', 'price', 'currency', 'is_active', 'created_at')


class CreditPurchaseSerializer(serializers.ModelSerializer):
    package = CreditPackageSerializer(read_only=True)

    class Meta:
        model = CreditPurchase
        fields = ('id', 'package', 'status', 'credits_amount', 'amount_paid', 'currency', 'created_at', 'completed_at')


class UserConnectionSerializer(serializers.ModelSerializer):
    initiator = ParticipantSerializer(read_only=True)
    receiver = ParticipantSerializer(read_only=True)
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True, allow_null=True)

    class Meta:
        model = UserConnection
        fields = ('id', 'initiator', 'receiver', 'status', 'conversation_id', 'created_at', 'connected_at')

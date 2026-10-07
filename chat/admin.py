from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Block,
    Conversation,
    CreditBalance,
    CreditPackage,
    CreditPurchase,
    Message,
    UserConnection,
)


class MessageInline(TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'content', 'created_at')
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ('id', 'participant_list', 'created_at')
    readonly_fields = ('created_at',)
    inlines = [MessageInline]

    @admin.display(description='Participants')
    def participant_list(self, obj):
        return ', '.join(u.email for u in obj.participants.all())


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'short_content', 'created_at')
    list_filter = ('conversation',)
    search_fields = ('sender__email', 'content')
    readonly_fields = ('created_at',)

    @admin.display(description='Content')
    def short_content(self, obj):
        return obj.content[:60] + ('…' if len(obj.content) > 60 else '')


@admin.register(CreditBalance)
class CreditBalanceAdmin(ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('updated_at',)


@admin.register(CreditPackage)
class CreditPackageAdmin(ModelAdmin):
    list_display = ('name', 'credits_amount', 'price', 'currency', 'is_active', 'created_at')
    list_filter = ('is_active', 'currency')
    search_fields = ('name',)


@admin.register(CreditPurchase)
class CreditPurchaseAdmin(ModelAdmin):
    list_display = ('user', 'package', 'status', 'credits_amount', 'amount_paid', 'currency', 'created_at', 'completed_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('user__email', 'stripe_session_id', 'stripe_payment_intent_id')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(UserConnection)
class UserConnectionAdmin(ModelAdmin):
    list_display = ('id', 'initiator', 'receiver', 'status', 'created_at', 'connected_at')
    list_filter = ('status',)
    search_fields = ('initiator__email', 'receiver__email')
    readonly_fields = ('created_at', 'connected_at')


@admin.register(Block)
class BlockAdmin(ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')
    search_fields = ('blocker__email', 'blocked__email')
    readonly_fields = ('created_at',)


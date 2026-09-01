from django.urls import path

from .views import (
    BlockUserAPIView,
    ConnectionListAPIView,
    ConversationListAPIView,
    ConversationWithUserAPIView,
    CreditBalanceAPIView,
    MessageHistoryAPIView,
    ScanQRAPIView,
    CreditPackageListAPIView,
    CreditPurchaseCreateAPIView,
    CreditPurchaseHistoryAPIView,
    StripeWebhookAPIView,
    StripeSuccessAPIView,
    StripeCancelAPIView,
)

urlpatterns = [
    # QR scan & connections
    path('scan/<slug:slug>/', ScanQRAPIView.as_view(), name='scan-qr'),
    path('connections/', ConnectionListAPIView.as_view(), name='connection-list'),

    # Conversations (gated behind active connection)
    path('users/<int:user_id>/', ConversationWithUserAPIView.as_view(), name='chat-with-user'),
    path('users/<int:user_id>/block/', BlockUserAPIView.as_view(), name='block-user'),
    path('conversations/', ConversationListAPIView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/messages/', MessageHistoryAPIView.as_view(), name='message-history'),

    # Credits
    path('credits/', CreditBalanceAPIView.as_view(), name='credit-balance'),
    path('credits/packages/', CreditPackageListAPIView.as_view(), name='credit-packages'),
    path('credits/purchase/', CreditPurchaseCreateAPIView.as_view(), name='credit-purchase'),
    path('credits/history/', CreditPurchaseHistoryAPIView.as_view(), name='credit-history'),
    path('credits/webhook/', StripeWebhookAPIView.as_view(), name='stripe-webhook'),
    path('credits/success/', StripeSuccessAPIView.as_view(), name='stripe-success'),
    path('credits/cancel/', StripeCancelAPIView.as_view(), name='stripe-cancel'),
]

from django.urls import path

from .views import (
    AmbassadorBookingAPIView,
    AmbassadorQRCodeAPIView,
    AmbassadorSlotsAPIView,
    CurrentAmbassadorBookingAPIView,
    CurrentUserOrdersAPIView,
    LoginAPIView,
    MeAPIView,
    QRCodeAPIView,
    ResendOtpAPIView,
    SpeacialEventAPIView,
    SupportAPIView,
    VerifyOtpAPIView,
    RingExchangePolicyAPIView,
    RingExchangeAPIView,
    RingExchangeDetailAPIView,
    RingExchangeStripeWebhookAPIView,
    RefundPolicyAPIView,
    RefundAPIView,
    RefundDetailAPIView,
)


urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='login'),
    path('resend-otp/', ResendOtpAPIView.as_view(), name='resend-otp'),
    path('verify-otp/', VerifyOtpAPIView.as_view(), name='verify-otp'),
    path('me/', MeAPIView.as_view(), name='me'),
    path('me/qr/', QRCodeAPIView.as_view(), name='me-qr'),
    path('support/', SupportAPIView.as_view(), name='support'),
    path('membership-status/', CurrentUserOrdersAPIView.as_view(), name='membership-status'),
    path('special-event/', SpeacialEventAPIView.as_view(), name='special-event'),
    path('ambassador/slots/', AmbassadorSlotsAPIView.as_view(), name='ambassador-slots'),
    path('ambassador/book/', AmbassadorBookingAPIView.as_view(), name='ambassador-book'),
    path('ambassador/booking/', CurrentAmbassadorBookingAPIView.as_view(), name='ambassador-booking'),
    path('ambassador/me/qr/', AmbassadorQRCodeAPIView.as_view(), name='ambassador-me-qr'),
    path('ring-exchange/policy/', RingExchangePolicyAPIView.as_view(), name='ring-exchange-policy'),
    path('ring-exchange/', RingExchangeAPIView.as_view(), name='ring-exchange-list-create'),
    # path('ring-exchange/<int:pk>/', RingExchangeDetailAPIView.as_view(), name='ring-exchange-detail'),
    path('ring-exchange/webhook/', RingExchangeStripeWebhookAPIView.as_view(), name='ring-exchange-webhook'),
    path('refund/policy/', RefundPolicyAPIView.as_view(), name='refund-policy'),
    path('refund/', RefundAPIView.as_view(), name='refund-list-create'),
    # path('refund/<int:pk>/', RefundDetailAPIView.as_view(), name='refund-detail'),
]


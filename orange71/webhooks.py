import stripe
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import RingExchangeRequest
from chat.models import CreditBalance, CreditPurchase


class UnifiedStripeWebhookAPIView(APIView):
    """
    POST /api/stripe/webhook/

    Unified Stripe Webhook handler that processes events for Credit Purchases,
    Ring Exchange payments, and any future Stripe integrations.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Stripe Webhook"],
        summary="Unified Stripe Webhook Callback",
        description="Processes incoming Stripe webhook events for Credit Purchases and Ring Exchange payments.",
        request=None,
        responses=None,
    )
    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        if not webhook_secret:
            return Response(
                {"detail": "Webhook secret not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            event = stripe.Webhook.construct_event(
                payload=payload, sig_header=sig_header, secret=webhook_secret
            )
        except ValueError:
            return Response({"detail": "Invalid payload."}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            return self._handle_checkout_session_completed(data_object)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

    def _handle_checkout_session_completed(self, data_object):
        session_id = data_object.get("id")
        payment_intent = data_object.get("payment_intent")

        if not session_id:
            return Response({"detail": "Missing session id."}, status=status.HTTP_400_BAD_REQUEST)

        event_handled = False

        # 1. Check for Credit Purchase
        purchase = (
            CreditPurchase.objects.filter(stripe_session_id=session_id)
            .select_related("user", "package")
            .first()
        )
        if purchase:
            event_handled = True
            if purchase.status != CreditPurchase.STATUS_COMPLETED:
                purchase.status = CreditPurchase.STATUS_COMPLETED
                purchase.stripe_payment_intent_id = payment_intent
                purchase.completed_at = timezone.now()
                purchase.save(update_fields=["status", "stripe_payment_intent_id", "completed_at"])

                if purchase.user and purchase.package:
                    balance = CreditBalance.get_or_create_for_user(purchase.user)
                    balance.add(purchase.credits_amount)

        # 2. Check for Ring Exchange Request
        exchange = RingExchangeRequest.objects.filter(stripe_session_id=session_id).first()
        if exchange:
            event_handled = True
            if exchange.payment_status != RingExchangeRequest.PAYMENT_PAID:
                exchange.payment_status = RingExchangeRequest.PAYMENT_PAID
                exchange.status = RingExchangeRequest.STATUS_APPROVED
                exchange.stripe_payment_intent_id = payment_intent
                exchange.save(
                    update_fields=["payment_status", "status", "stripe_payment_intent_id", "updated_at"]
                )

        if not event_handled:
            # Event is acknowledged even if no session match is found in DB
            return Response({"detail": "Session not matched to any active record."}, status=status.HTTP_200_OK)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

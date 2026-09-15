from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import RingExchangeRequest
from chat.models import CreditBalance, CreditPackage, CreditPurchase
from orange71.webhooks import UnifiedStripeWebhookAPIView

User = get_user_model()


class UnifiedStripeWebhookTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="webhook_user@example.com",
            name="Webhook User",
            password="Password123!",
        )
        self.package = CreditPackage.objects.create(
            name="Starter Pack",
            credits_amount=100,
            price=9.99,
            currency="USD",
            is_active=True,
        )

    @override_settings(STRIPE_WEBHOOK_SECRET="")
    def test_webhook_secret_not_configured(self):
        url = "/api/stripe/webhook/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret")
    @patch("stripe.Webhook.construct_event")
    def test_credit_purchase_webhook(self, mock_construct_event):
        purchase = CreditPurchase.objects.create(
            user=self.user,
            package=self.package,
            stripe_session_id="cs_test_credit_123",
            credits_amount=100,
            amount_paid=999,
            currency="USD",
            status=CreditPurchase.STATUS_PENDING,
        )

        mock_construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_credit_123",
                    "payment_intent": "pi_test_credit_456",
                    "metadata": {"type": "credit_purchase"},
                }
            },
        }

        url = "/api/stripe/webhook/"
        response = self.client.post(
            url,
            data={"dummy": "payload"},
            format="json",
            HTTP_STRIPE_SIGNATURE="dummy_sig",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase.refresh_from_db()
        self.assertEqual(purchase.status, CreditPurchase.STATUS_COMPLETED)
        self.assertEqual(purchase.stripe_payment_intent_id, "pi_test_credit_456")

        balance = CreditBalance.objects.get(user=self.user)
        self.assertEqual(balance.balance, CreditBalance.MOCK_STARTING_CREDITS + 100)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret")
    @patch("stripe.Webhook.construct_event")
    def test_ring_exchange_webhook(self, mock_construct_event):
        exchange = RingExchangeRequest.objects.create(
            user=self.user,
            order_id="9991",
            original_item_name="Gold Ring",
            original_size="7",
            desired_size="8",
            purchase_date=timezone.now(),
            stripe_session_id="cs_test_ring_123",
            payment_status=RingExchangeRequest.PAYMENT_PENDING,
            status=RingExchangeRequest.STATUS_PAYMENT_PENDING,
        )

        mock_construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_ring_123",
                    "payment_intent": "pi_test_ring_456",
                    "metadata": {"type": "ring_exchange"},
                }
            },
        }

        url = "/api/stripe/webhook/"
        response = self.client.post(
            url,
            data={"dummy": "payload"},
            format="json",
            HTTP_STRIPE_SIGNATURE="dummy_sig",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        exchange.refresh_from_db()
        self.assertEqual(exchange.payment_status, RingExchangeRequest.PAYMENT_PAID)
        self.assertEqual(exchange.status, RingExchangeRequest.STATUS_APPROVED)
        self.assertEqual(exchange.stripe_payment_intent_id, "pi_test_ring_456")

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret")
    @patch("stripe.Webhook.construct_event")
    def test_unmatched_session_webhook(self, mock_construct_event):
        mock_construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_unknown_session",
                    "payment_intent": "pi_unknown",
                }
            },
        }

        url = "/api/stripe/webhook/"
        response = self.client.post(
            url,
            data={"dummy": "payload"},
            format="json",
            HTTP_STRIPE_SIGNATURE="dummy_sig",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["detail"], "Session not matched to any active record.")

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import RefundPolicy, RefundRequest, RingExchangeRequest

User = get_user_model()


class RefundPolicyAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            name="Test User",
            password="Password123!",
        )
        self.policy = RefundPolicy.get_policy()
        self.policy.refund_deadline_days = 21
        self.policy.save()

    def test_refund_policy_unauthenticated(self):
        url = "/api/auth/refund/policy/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refund_policy_no_purchase(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/refund/policy/"
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["refund_deadline_days"], 21)
        self.assertIn("return_shipping_address", data)
        self.assertIn("instructions", data)
        self.assertIn("restocking_fee_percentage", data)
        self.assertIn("currency", data)
        self.assertIn("updated_at", data)
        self.assertIsNone(data["user_purchase_date"])
        self.assertIsNone(data["user_refund_deadline"])
        self.assertIsNone(data["refund_deadline_date"])
        self.assertIsNone(data["return_deadline"])
        self.assertIsNone(data["is_eligible"])

    def test_refund_policy_with_db_purchase(self):
        self.client.force_authenticate(user=self.user)
        purchase_date = timezone.now() - timedelta(days=5)

        RefundRequest.objects.create(
            user=self.user,
            order_id="1001",
            item_name="Amore Ring",
            reason="Size mismatch",
            purchase_date=purchase_date,
            original_price=5000,
            refund_amount=5000,
            return_deadline=purchase_date + timedelta(days=21),
        )

        url = "/api/auth/refund/policy/"
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        expected_deadline = (purchase_date + timedelta(days=21)).isoformat()
        self.assertEqual(data["user_purchase_date"], purchase_date.isoformat())
        self.assertEqual(data["user_refund_deadline"], expected_deadline)
        self.assertEqual(data["refund_deadline_date"], expected_deadline)
        self.assertEqual(data["return_deadline"], expected_deadline)
        self.assertTrue(data["is_eligible"])

    def test_refund_policy_with_woocommerce_purchase(self):
        self.client.force_authenticate(user=self.user)
        order_date_str = "2026-08-20T10:00:00Z"

        mock_wc = patch("authentication.views.get_wc_api")
        mock_fetch = patch(
            "authentication.views.CurrentUserOrdersAPIView._fetch_orders_for_email",
            return_value=[{"id": 999, "date_created": order_date_str}],
        )

        url = "/api/auth/refund/policy/"
        with mock_wc as m_wc, mock_fetch:
            m_wc.return_value = True
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["user_purchase_date"].startswith("2026-08-20T10:00:00"))
        self.assertTrue(data["user_refund_deadline"].startswith("2026-09-10T10:00:00"))
        self.assertTrue(data["refund_deadline_date"].startswith("2026-09-10T10:00:00"))

    def test_refund_policy_with_naive_date(self):
        self.client.force_authenticate(user=self.user)
        naive_order_date_str = "2026-08-20 10:00:00"

        mock_wc = patch("authentication.views.get_wc_api")
        mock_fetch = patch(
            "authentication.views.CurrentUserOrdersAPIView._fetch_orders_for_email",
            return_value=[{"id": 999, "date_created": naive_order_date_str}],
        )

        url = "/api/auth/refund/policy/"
        with mock_wc as m_wc, mock_fetch:
            m_wc.return_value = True
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsNotNone(data["user_refund_deadline"])
        self.assertTrue(data["user_purchase_date"].startswith("2026-08-20T10:00:00"))


class RingExchangePolicyAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="exchange_user@example.com",
            name="Exchange User",
            password="Password123!",
        )

    def test_ring_exchange_policy_unauthenticated(self):
        url = "/api/auth/ring-exchange/policy/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ring_exchange_policy_no_purchase(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/ring-exchange/policy/"
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["free_exchange_days"], 14)
        self.assertIn("charge_type", data)
        self.assertIn("fixed_fee_amount", data)
        self.assertIn("fee_percentage", data)
        self.assertIn("shipping_cost", data)
        self.assertIsNone(data["user_purchase_date"])
        self.assertIsNone(data["user_free_exchange_deadline"])
        self.assertIsNone(data["free_exchange_deadline_date"])
        self.assertIsNone(data["exchange_deadline_date"])
        self.assertIsNone(data["is_within_free_window"])

    def test_ring_exchange_policy_with_woocommerce_purchase(self):
        self.client.force_authenticate(user=self.user)
        purchase_dt = timezone.now() - timedelta(days=2)
        order_date_str = purchase_dt.isoformat()

        mock_wc = patch("authentication.views.get_wc_api")
        mock_fetch = patch(
            "authentication.views.CurrentUserOrdersAPIView._fetch_orders_for_email",
            return_value=[{"id": 888, "date_created": order_date_str}],
        )

        url = "/api/auth/ring-exchange/policy/"
        with mock_wc as m_wc, mock_fetch:
            m_wc.return_value = True
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        expected_deadline = (purchase_dt + timedelta(days=14)).isoformat()
        self.assertEqual(data["user_purchase_date"], purchase_dt.isoformat())
        self.assertEqual(data["user_free_exchange_deadline"], expected_deadline)
        self.assertEqual(data["free_exchange_deadline_date"], expected_deadline)
        self.assertEqual(data["exchange_deadline_date"], expected_deadline)
        self.assertTrue(data["is_within_free_window"])


class FloatOriginalPriceValidationTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="float_test@example.com",
            name="Float Test User",
            password="Password123!",
        )

    def test_refund_request_with_float_original_price(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/refund/"
        payload = {
            "order_id": "9999",
            "item_name": "Silver Ring",
            "reason": "Wrong size",
            "original_price": 99.99,
        }
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["original_price"], 99.99)

    def test_ring_exchange_request_with_float_original_price(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/ring-exchange/"
        payload = {
            "order_id": "8888",
            "original_item_name": "Gold Ring",
            "original_size": "7",
            "desired_size": "8",
            "is_damaged": False,
            "original_price": 149.50,
        }
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["original_price"], 149.50)

    def test_refund_request_with_naive_purchase_date(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/refund/"
        payload = {
            "order_id": "9998",
            "item_name": "Silver Ring",
            "reason": "Defective",
            "purchase_date": "2026-08-20T10:00:00",
            "original_price": 50.00,
        }
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["original_price"], 50.00)

    def test_ring_exchange_request_with_naive_purchase_date(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/ring-exchange/"
        payload = {
            "order_id": "8887",
            "original_item_name": "Gold Ring",
            "original_size": "7",
            "desired_size": "8",
            "is_damaged": False,
            "purchase_date": "2026-08-20T10:00:00",
            "original_price": 100.00,
        }
        with patch("authentication.views.get_wc_api", return_value=None):
            response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["original_price"], 100.00)

    def test_refund_request_woocommerce_price_preservation(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/auth/refund/"
        payload = {
            "order_id": "1230",
            "item_name": "Wingman - Ring Sizer",
            "item_size": "ring-sizer",
            "reason": "test",
            "purchase_date": "2026-09-12T04:50:08.101Z",
            "original_price": 29.99,
        }

        mock_wc = patch("authentication.views.get_wc_api")
        mock_fetch = patch(
            "authentication.views.CurrentUserOrdersAPIView._fetch_orders_for_email",
            return_value=[{
                "id": 1230,
                "date_created": "2026-09-05T13:36:25Z",
                "line_items": [{
                    "name": "Wingman - Ring Sizer",
                    "price": "29.99",
                    "total": "29.99"
                }]
            }],
        )

        with mock_wc as m_wc, mock_fetch:
            m_wc.return_value = True
            response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["original_price"], 29.99)
        self.assertEqual(data["refund_amount"], 29.99)




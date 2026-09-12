import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db import IntegrityError
from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.utils import timezone

from .serializers import (
    AccessTokenSerializer,
    AmbassadorBookSerializer,
    AmbassadorBookingSerializer,
    AmbassadorSlotSerializer,
    LoginSerializer,
    OtpSentSerializer,
    RefreshTokenSerializer,
    SpeacialEventSerializer,
    SupportSerializer,
    TokenPairSerializer,
    UserSerializer,
    VerifyOtpSerializer,
    UserUpdateSerializer,
    RingExchangePolicySerializer,
    RingExchangeRequestCreateSerializer,
    RingExchangeRequestSerializer,
    RingExchangeTrackingUpdateSerializer,
    RefundPolicySerializer,
    RefundRequestCreateSerializer,
    RefundRequestSerializer,
    RefundTrackingUpdateSerializer,
)
from .woocommerce_client import get_wc_api
from .order_serializers import OrderSerializer, SimpleOrderSerializer
from .utils import fetch_users

User = get_user_model()
from .models import (
    AmbassadorBooking,
    AmbassadorSlot,
    SpeacialEvent,
    Support,
    RingExchangePolicy,
    RingExchangeRequest,
    RefundPolicy,
    RefundRequest,
)

OTP_EXPIRY_MINUTES = 10
AUTH_TAG = "Authentication"
TOKEN_TAG = "Tokens"
PROFILE_TAG = "Profile"
SPECIAL_EVENT_TAG = "Special Event"
SUPPORT_TAG = "Support"


def generate_otp():
    return f"{secrets.randbelow(10000):04d}"


def send_otp_email(user, otp):
    subject = f"{otp} is your Amore Rings verification code"
    user_name = getattr(user, "name", "") or user.email.split("@")[0]

    text_content = (
        f"Hi {user_name},\n\n"
        f"Your verification code for Amore Rings is: {otp}\n\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes. Please do not share this code with anyone.\n\n"
        f"Best regards,\nThe Amore Rings Team"
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Amore Rings Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 40px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 520px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);">
          <!-- Header -->
          <tr>
            <td align="center" style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 36px 20px;">
              <h1 style="margin: 0; color: #f8fafc; font-size: 26px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;">
                AMORE RINGS
              </h1>
              <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 13px; letter-spacing: 1px; text-transform: uppercase;">
                Exclusive Customer Access
              </p>
            </td>
          </tr>
          
          <!-- Content -->
          <tr>
            <td style="padding: 40px 32px; color: #334155;">
              <p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.5; color: #1e293b; font-weight: 600;">
                Hi {user_name},
              </p>
              <p style="margin: 0 0 28px 0; font-size: 15px; line-height: 1.6; color: #475569;">
                Thank you for using Amore Rings. Use the verification code below to log in to your account:
              </p>
              
              <!-- OTP Box -->
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-bottom: 28px;">
                <tr>
                  <td align="center" style="background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 24px;">
                    <div style="font-family: 'Courier New', Courier, monospace; font-size: 38px; font-weight: 800; letter-spacing: 10px; color: #0f172a; margin-left: 10px;">
                      {otp}
                    </div>
                  </td>
                </tr>
              </table>
              
              <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px; padding: 12px 16px; margin-bottom: 28px;">
                <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #92400e;">
                  ⏱ <strong>Note:</strong> This code is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong>. Please do not share this code with anyone.
                </p>
              </div>
              
              <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #64748b;">
                If you did not request this verification code, you can safely ignore this email.
              </p>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td align="center" style="background-color: #f8fafc; padding: 24px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 12px; line-height: 1.5;">
              <p style="margin: 0 0 4px 0;">&copy; Amore Rings. All rights reserved.</p>
              <p style="margin: 0;">This is an automated message, please do not reply to this email.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    send_mail(
        subject=subject,
        message=text_content,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        html_message=html_content,
        fail_silently=False,
    )


def issue_otp(user):
    otp = generate_otp()
    user.otp = otp
    user.otp_generated_at = timezone.now()
    user.save(update_fields=["otp", "otp_generated_at"])
    send_otp_email(user, otp)
    return otp


def sync_user_from_wordpress(email):
    user_info = fetch_users(email)

    if not isinstance(user_info, dict):
        return None, user_info

    user = User.objects.filter(email=email).first()
    name = user_info.get("name") or email.split("@")[0]

    if user is None:
        user = User.objects.create_user(
            email=email,
            name=name,
            nickname=user_info.get("nickname", ""),
            website=user_info.get("url", ""),
        )
    else:
        changed_fields = []
        if name and user.name != name:
            user.name = name
            changed_fields.append("name")
        nickname = user_info.get("nickname", "")
        if nickname != user.nickname:
            user.nickname = nickname
            changed_fields.append("nickname")
        website = user_info.get("url", "")
        if website != user.website:
            user.website = website
            changed_fields.append("website")
        if changed_fields:
            user.save(update_fields=changed_fields)

    if user_info.get("avatar_urls"):
        user.profile_picture = user_info["avatar_urls"].get("128", "")
        user.save(update_fields=["profile_picture"])

    return user, user_info


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Request OTP login",
        description="Looks up the email in WordPress, syncs the user profile, creates an OTP, and emails it to the user.",
        request=LoginSerializer,
        responses=OtpSentSerializer,
    )
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, user_info = sync_user_from_wordpress(email)

        if user_info == "not_found":
            return Response(
                {"detail": "No user found with the provided email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user is None:
            return Response(
                {"detail": "Failed to fetch user data from WordPress API."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            issue_otp(user)
        except smtplib.SMTPAuthenticationError:
            return Response(
                {
                    "detail": "Gmail authentication failed. Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except smtplib.SMTPException:
            return Response(
                {"detail": "SMTP email delivery failed. Check Gmail SMTP settings."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"detail": "OTP email could not be sent."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "detail": "Verification code sent to your email.",
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )


class ResendOtpAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Resend OTP",
        description="Reissues a fresh OTP for the email address and sends it to the user again.",
        request=LoginSerializer,
        responses=OtpSentSerializer,
    )
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, user_info = sync_user_from_wordpress(email)

        if user_info == "not_found":
            return Response(
                {"detail": "No user found with the provided email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user is None:
            return Response(
                {"detail": "Failed to fetch user data from WordPress API."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            issue_otp(user)
        except smtplib.SMTPAuthenticationError:
            return Response(
                {
                    "detail": "Gmail authentication failed. Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except smtplib.SMTPException:
            return Response(
                {"detail": "SMTP email delivery failed. Check Gmail SMTP settings."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"detail": "OTP email could not be sent."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "detail": "Verification code sent to your email.",
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )


class VerifyOtpAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Verify OTP and issue JWTs",
        description="Validates the OTP for the email address and returns a JWT refresh/access token pair.",
        request=VerifyOtpSerializer,
        responses=TokenPairSerializer,
    )
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        if not email or not otp:
            return Response(
                {"detail": "Email and otp are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email=email).first()
        if user is None:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.otp or user.otp != otp:
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.otp_generated_at and timezone.now() - user.otp_generated_at > timedelta(
            minutes=OTP_EXPIRY_MINUTES
        ):
            user.otp = None
            user.otp_generated_at = None
            user.save(update_fields=["otp", "otp_generated_at"])
            return Response(
                {"detail": "OTP has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.otp = None
        user.otp_generated_at = None
        user.save(update_fields=["otp", "otp_generated_at"])

        token = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user, context={"request": request}).data,
            "refresh": str(token),
            "access": str(token.access_token),
        })


class RefreshTokenAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=[TOKEN_TAG],
        summary="Refresh access token",
        description="Exchanges a valid refresh token for a new access token.",
        request=RefreshTokenSerializer,
        responses=AccessTokenSerializer,
    )
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh)
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({"access": str(token.access_token)})


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=[PROFILE_TAG],
        summary="Get current user",
        description="Returns the authenticated user profile from the JWT token.",
        responses=UserSerializer,
    )
    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    @extend_schema(
        tags=[PROFILE_TAG],
        summary="Update current user",
        description="Partially update the current user; supports `name` and `profile_picture_local` upload.",
        request=UserUpdateSerializer,
        responses=UserSerializer,
    )
    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_fields = []
        name = serializer.validated_data.get("name")
        if name is not None and request.user.name != name:
            request.user.name = name
            updated_fields.append("name")

        profile_picture_local = serializer.validated_data.get("profile_picture_local")
        if profile_picture_local is not None:
            request.user.profile_picture_local = profile_picture_local
            updated_fields.append("profile_picture_local")

        if updated_fields:
            request.user.save(update_fields=updated_fields)

        return Response(UserSerializer(request.user, context={"request": request}).data)


class SpeacialEventAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[SPECIAL_EVENT_TAG],
        summary="Get special event",
        description="Returns the single special event URL.",
        responses=SpeacialEventSerializer,
    )
    def get(self, request):
        event = SpeacialEvent.objects.first()
        if event is None:
            return Response(
                {"detail": "Special event is not configured."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SpeacialEventSerializer({"special_event": event.special_event})
        return Response(serializer.data)


class SupportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[SUPPORT_TAG],
        summary="Submit support request",
        description="Authenticated users can submit a support request. The request is stored and emailed to admin.",
        request=SupportSerializer,
        responses=SupportSerializer,
    )
    def post(self, request):
        serializer = SupportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        support = serializer.save()

        try:
            send_mail(
                subject="New Support Request - Orange71",
                message=(
                    f"Full Name: {support.full_name}\n"
                    f"Email: {support.email}\n\n"
                    f"How can I help you?\n{support.how_can_i_help_you}"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[settings.SUPPORT_ADMIN_EMAIL],
                fail_silently=False,
            )
        except smtplib.SMTPAuthenticationError:
            return Response(
                {
                    "detail": "Gmail authentication failed. Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except smtplib.SMTPException:
            return Response(
                {"detail": "SMTP email delivery failed. Check Gmail SMTP settings."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"detail": "Support request saved, but email could not be sent."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(SupportSerializer(support).data, status=status.HTTP_201_CREATED)


class CurrentUserOrdersAPIView(APIView):
    """
    GET /api/auth/membership-status/

    Return the current user's WooCommerce orders and detailed line items.

    Response Example (200 OK):
    [
        {
            "id": 1001,
            "status": "completed",
            "date_created": "2026-08-20T10:00:00Z",
            "total": "99.00",
            "currency": "USD",
            "membersip_type": "member",
            "member_since": "2026-05-22T03:07:33Z",
            "items": [
                {
                    "id": 501,
                    "product_id": 12,
                    "name": "Amore Silver Ring",
                    "size": "7",
                    "price": "99.00",
                    "total": "99.00"
                }
            ]
        }
    ]
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Membership Status"],
        summary="Get membership status",
        description=(
            "Returns the authenticated user membership status and detailed WooCommerce order line items.\n\n"
            "**Response Format Example (200 OK)**:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"id\": 1001,\n"
            "    \"status\": \"completed\",\n"
            "    \"date_created\": \"2026-08-20T10:00:00Z\",\n"
            "    \"total\": \"99.00\",\n"
            "    \"currency\": \"USD\",\n"
            "    \"membersip_type\": \"member\",\n"
            "    \"member_since\": \"2026-05-22T03:07:33Z\",\n"
            "    \"items\": [\n"
            "      {\n"
            "        \"id\": 501,\n"
            "        \"product_id\": 12,\n"
            "        \"name\": \"Amore Silver Ring\",\n"
            "        \"size\": \"7\",\n"
            "        \"price\": \"99.00\",\n"
            "        \"total\": \"99.00\"\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "]\n"
            "```"
        ),
        responses=SimpleOrderSerializer(many=True),
    )
    def get(self, request):
        wc = get_wc_api()
        if wc is None:
            return Response(
                {"detail": "WooCommerce not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        email = request.user.email

        orders = self._fetch_orders_for_email(wc, email)
        product_cache = {}

        # Build enriched order details
        simplified = []
        for o in orders:
            items = []
            for li in o.get("line_items", []):
                size = None
                meta_data = li.get("meta_data") or []
                for m in meta_data:
                    key = (m.get("display_key") or m.get("key") or "").strip().lower()
                    if key in {"size", "pa_size", "_size", "select size"}:
                        size = m.get("value")
                        break

                items.append({
                    "id": li.get("id"),
                    "product_id": li.get("product_id"),
                    "name": li.get("name"),
                    "size": size,
                    "price": str(li.get("price") or li.get("total") or "0"),
                    "total": str(li.get("total") or "0"),
                })

            simplified.append({
                "id": o.get("id"),
                "status": o.get("status"),
                "date_created": o.get("date_created"),
                "total": str(o.get("total") or "0"),
                "currency": o.get("currency", "USD"),
                "items": items,
                "membersip_type": request.user.account_type,
                "member_since": request.user.date_joined,
            })

        serializer = SimpleOrderSerializer(simplified, many=True)
        return Response(serializer.data)

    # def _get_product_details(self, wc, product_id, product_cache):
    #     if not product_id:
    #         return None

    #     if product_id in product_cache:
    #         return product_cache[product_id]

    #     try:
    #         response = wc.get(f'products/{product_id}')
    #         response.raise_for_status()
    #         product = response.json() or {}
    #     except Exception:
    #         product_cache[product_id] = None
    #         return None

    #     image = None
    #     images = product.get('images') or []
    #     if images:
    #         image = images[0].get('src')

    #     size = self._get_product_size(product)

    #     product_details = {
    #         'id': product.get('id'),
    #         'name': product.get('name'),
    #         'size': size,
    #         'sku': product.get('sku'),
    #         'slug': product.get('slug'),
    #         'permalink': product.get('permalink'),
    #         'price': product.get('price'),
    #         'regular_price': product.get('regular_price'),
    #         'sale_price': product.get('sale_price'),
    #         'stock_status': product.get('stock_status'),
    #         'image': image,
    #     }
    #     product_cache[product_id] = product_details
    #     return product_details

    def _get_product_size(self, product):
        attributes = product.get("attributes") or []
        for attribute in attributes:
            attribute_name = (attribute.get("name") or "").strip().lower()
            attribute_slug = (attribute.get("slug") or "").strip().lower()
            if attribute_name == "size" or attribute_slug == "pa_size":
                options = attribute.get("options") or []
                if options:
                    return options[0]
                return attribute.get("option")

        meta_data = product.get("meta_data") or []
        for meta in meta_data:
            key = (meta.get("key") or "").strip().lower()
            if key in {"size", "_size"}:
                value = meta.get("value")
                if value:
                    return value

        return None

    def _fetch_orders_for_email(self, wc, email):
        try:
            customer_response = wc.get("customers", params={"email": email})
            customer_response.raise_for_status()
        except Exception:
            customer_response = None

        if customer_response is not None:
            customers = customer_response.json() or []
            if customers:
                customer_id = customers[0].get("id")
                try:
                    orders_response = wc.get(
                        "orders", params={"customer": customer_id, "per_page": 100}
                    )
                    orders_response.raise_for_status()
                    orders = orders_response.json() or []
                    if orders:
                        return orders
                except Exception:
                    pass

        return self._fetch_orders_by_billing_email(wc, email)

    def _fetch_orders_by_billing_email(self, wc, email):
        collected_orders = []
        page = 1

        while True:
            try:
                response = wc.get("orders", params={"per_page": 100, "page": page})
                response.raise_for_status()
            except Exception:
                break

            page_orders = response.json() or []
            if not page_orders:
                break

            for order in page_orders:
                billing = order.get("billing") or {}
                if (
                    billing.get("email") or ""
                ).strip().lower() == email.strip().lower():
                    collected_orders.append(order)

            if len(page_orders) < 100:
                break

            page += 1

        return collected_orders


class QRCodeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[PROFILE_TAG],
        summary="Get my QR code image",
        description=(
            "Returns the authenticated user's QR code as a PNG image. "
            "The QR encodes the user's unique slug. "
            "The mobile app scans this and calls POST /api/chat/scan/<slug>/ to initiate a connection."
        ),
        responses={200: bytes},
    )
    def get(self, request):
        user = request.user
        if not user.qr_code:
            return Response(
                {"detail": "QR code not yet generated. Try logging in again."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(user.qr_code.open("rb"), content_type="image/png")


AMBASSADOR_TAG = "Ambassador"


class AmbassadorSlotsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[AMBASSADOR_TAG],
        summary="List available ambassador time slots",
        description=(
            "Returns future and currently available AmbassadorSlots that the authenticated user can book. "
            "Optionally filter by a specific date using the `date` query parameter (YYYY-MM-DD)."
        ),
        parameters=[
            OpenApiParameter(
                name="date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter slots by a specific date (YYYY-MM-DD). If omitted, returns all future available slots.",
                required=False,
            ),
        ],
        responses=AmbassadorSlotSerializer(many=True),
    )
    def get(self, request):
        from datetime import datetime, timedelta, date as date_type

        now = timezone.now()
        slots = AmbassadorSlot.objects.filter(
            is_available=True,
            start_time__gte=now,
        )

        selected_date = request.query_params.get("date")
        if selected_date:
            try:
                target_date = date_type.fromisoformat(selected_date)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not isinstance(target_date, date_type):
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            day_start = timezone.make_aware(
                datetime.combine(target_date, datetime.min.time())
            )
            day_end = day_start + timedelta(days=1)
            slots = slots.filter(start_time__gte=day_start, start_time__lt=day_end)

        serializer = AmbassadorSlotSerializer(slots, many=True)
        return Response(serializer.data)


class AmbassadorBookingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[AMBASSADOR_TAG],
        summary="Book an ambassador slot",
        description=(
            "Book an available AmbassadorSlot for the authenticated user. "
            "Once booked, the slot is no longer available to others."
        ),
        request=AmbassadorBookSerializer,
        responses=AmbassadorBookingSerializer,
    )
    def post(self, request):
        serializer = AmbassadorBookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot_id = serializer.validated_data["slot_id"]

        try:
            slot = AmbassadorSlot.objects.get(pk=slot_id)
        except AmbassadorSlot.DoesNotExist:
            return Response(
                {"detail": "Slot not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not slot.is_available:
            return Response(
                {"detail": "This slot is no longer available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if slot.start_time < timezone.now():
            return Response(
                {"detail": "This slot has already started."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if AmbassadorBooking.objects.filter(user=user).exists():
            return Response(
                {"detail": "You already have an ambassador booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if AmbassadorBooking.objects.filter(slot=slot).exists():
            return Response(
                {"detail": "This slot has already been booked."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                slot.is_available = False
                slot.save(update_fields=["is_available"])
                booking = AmbassadorBooking.objects.create(user=user, slot=slot)
        except IntegrityError:
            return Response(
                {
                    "detail": "This slot was just booked by someone else. Please try another slot."
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            send_mail(
                subject="Ambassador Booking Confirmed",
                message=(
                    f"Hi {user.name},\n\n"
                    f"Your brand ambassador booking is confirmed.\n"
                    f"Time: {slot.start_time.strftime('%Y-%m-%d %H:%M')} - {slot.end_time.strftime('%Y-%m-%d %H:%M')}"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[user.email],
                fail_silently=False,
            )
            send_mail(
                subject="New Ambassador Booking - Orange71",
                message=(
                    f"User {user.name} <{user.email}> has booked an ambassador slot.\n"
                    f"Time: {slot.start_time.strftime('%Y-%m-%d %H:%M')} - {slot.end_time.strftime('%Y-%m-%d %H:%M')}"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[settings.SUPPORT_ADMIN_EMAIL],
                fail_silently=False,
            )
        except Exception:
            pass

        response_serializer = AmbassadorBookingSerializer(
            booking, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CurrentAmbassadorBookingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[AMBASSADOR_TAG],
        summary="Get current ambassador booking",
        description=(
            "Returns the authenticated user's ambassador booking if one exists. "
            "The ambassador_link is only included after the booking is marked completed."
        ),
        responses=AmbassadorBookingSerializer,
    )
    def get(self, request):
        booking = AmbassadorBooking.objects.filter(user=request.user).first()
        if booking is None:
            return Response(
                {"detail": "No ambassador booking found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AmbassadorBookingSerializer(booking, context={"request": request})
        return Response(serializer.data)


class AmbassadorQRCodeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[AMBASSADOR_TAG],
        summary="Get my brand ambassador QR code image",
        description=(
            "Returns the brand ambassador QR code as a PNG image. "
            "Only available after the ambassador booking is marked completed. "
            "The QR encodes the ambassador_link URL."
        ),
        responses={200: bytes},
    )
    def get(self, request):
        booking = AmbassadorBooking.objects.filter(
            user=request.user,
            completed_at__isnull=False,
        ).first()
        if booking is None or not booking.brand_qr:
            return Response(
                {"detail": "Brand ambassador QR code not yet available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(booking.brand_qr.open("rb"), content_type="image/png")


RING_EXCHANGE_TAG = "Ring Exchange"


class RingExchangePolicyAPIView(APIView):
    """
    GET /api/auth/ring-exchange/policy/

    Return current dynamic ring exchange policy and user's calculated free exchange deadline date.

    Response Example (200 OK):
    {
        "free_exchange_days": 14,
        "charge_type": "shipping_only",
        "fixed_fee_amount": 1500,
        "fee_percentage": "20.00",
        "shipping_cost": 500,
        "currency": "usd",
        "updated_at": "2026-09-01T12:00:00Z",
        "user_purchase_date": "2026-08-20T10:00:00Z",
        "user_free_exchange_deadline": "2026-09-03T10:00:00Z",
        "free_exchange_deadline_date": "2026-09-03T10:00:00Z",
        "exchange_deadline_date": "2026-09-03T10:00:00Z",
        "is_within_free_window": true
    }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[RING_EXCHANGE_TAG],
        summary="Get active ring exchange policy",
        description=(
            "Returns the current dynamic ring exchange policy (free exchange days window, fee rules, shipping cost) "
            "and user's calculated free exchange deadline date.\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "{\n"
            "  \"free_exchange_days\": 14,\n"
            "  \"charge_type\": \"shipping_only\",\n"
            "  \"fixed_fee_amount\": 1500,\n"
            "  \"fee_percentage\": \"20.00\",\n"
            "  \"shipping_cost\": 500,\n"
            "  \"currency\": \"usd\",\n"
            "  \"updated_at\": \"2026-09-01T12:00:00Z\",\n"
            "  \"user_purchase_date\": \"2026-08-20T10:00:00Z\",\n"
            "  \"user_free_exchange_deadline\": \"2026-09-03T10:00:00Z\",\n"
            "  \"free_exchange_deadline_date\": \"2026-09-03T10:00:00Z\",\n"
            "  \"exchange_deadline_date\": \"2026-09-03T10:00:00Z\",\n"
            "  \"is_within_free_window\": true\n"
            "}\n"
            "```"
        ),
        responses=RingExchangePolicySerializer,
    )
    def get(self, request):
        policy = RingExchangePolicy.get_policy()
        serializer = RingExchangePolicySerializer(policy, context={'request': request})
        return Response(serializer.data)


class RingExchangeAPIView(APIView):
    """
    GET /api/auth/ring-exchange/
    List all ring exchange requests for the authenticated user.

    POST /api/auth/ring-exchange/
    Submit a ring exchange request. Auto-verifies order ownership with WooCommerce.

    Request Example:
    {
        "order_id": "1001",
        "original_item_name": "Amore Silver Ring",
        "original_size": "7",
        "desired_size": "8",
        "is_damaged": false,
        "purchase_date": "2026-08-28T00:00:00Z",
        "original_price": 5000
    }

    Response Example (201 Created - Free):
    {
        "id": 1,
        "order_id": "1001",
        "original_item_name": "Amore Silver Ring",
        "original_size": "7",
        "desired_size": "8",
        "is_damaged": false,
        "purchase_date": "2026-08-28T00:00:00Z",
        "original_price": 5000,
        "calculated_fee": 0,
        "shipping_cost": 0,
        "total_amount": 0,
        "currency": "usd",
        "is_within_free_window": true,
        "payment_status": "not_required",
        "stripe_session_id": null,
        "status": "approved",
        "user_tracking_number": null,
        "replacement_tracking_number": null,
        "notes": null,
        "created_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-01T12:00:00Z"
    }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[RING_EXCHANGE_TAG],
        summary="List my ring exchange requests",
        description=(
            "Returns all ring exchange requests submitted by the authenticated user.\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"id\": 1,\n"
            "    \"order_id\": \"1001\",\n"
            "    \"original_item_name\": \"Amore Silver Ring\",\n"
            "    \"original_size\": \"7\",\n"
            "    \"desired_size\": \"8\",\n"
            "    \"is_damaged\": false,\n"
            "    \"purchase_date\": \"2026-08-28T00:00:00Z\",\n"
            "    \"original_price\": 5000,\n"
            "    \"calculated_fee\": 0,\n"
            "    \"shipping_cost\": 0,\n"
            "    \"total_amount\": 0,\n"
            "    \"currency\": \"usd\",\n"
            "    \"is_within_free_window\": true,\n"
            "    \"payment_status\": \"not_required\",\n"
            "    \"stripe_session_id\": null,\n"
            "    \"status\": \"approved\",\n"
            "    \"user_tracking_number\": null,\n"
            "    \"replacement_tracking_number\": null,\n"
            "    \"notes\": null,\n"
            "    \"created_at\": \"2026-09-01T12:00:00Z\",\n"
            "    \"updated_at\": \"2026-09-01T12:00:00Z\"\n"
            "  }\n"
            "]\n"
            "```"
        ),
        responses=RingExchangeRequestSerializer(many=True),
    )
    def get(self, request):
        requests = RingExchangeRequest.objects.filter(user=request.user)
        serializer = RingExchangeRequestSerializer(requests, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=[RING_EXCHANGE_TAG],
        summary="Submit a ring exchange request",
        description=(
            "Submits a request to exchange a ring for a new size. "
            "Auto-verifies order ownership with WooCommerce and calculates fees based on policy.\n\n"
            "**Request Example**:\n"
            "```json\n"
            "{\n"
            "  \"order_id\": \"1001\",\n"
            "  \"original_item_name\": \"Amore Silver Ring\",\n"
            "  \"original_size\": \"7\",\n"
            "  \"desired_size\": \"8\",\n"
            "  \"is_damaged\": false,\n"
            "  \"purchase_date\": \"2026-08-28T00:00:00Z\",\n"
            "  \"original_price\": 5000\n"
            "}\n"
            "```\n\n"
            "**Response Example (Payment Required)**:\n"
            "```json\n"
            "{\n"
            "  \"id\": 2,\n"
            "  \"order_id\": \"1001\",\n"
            "  \"original_item_name\": \"Amore Silver Ring\",\n"
            "  \"original_size\": \"7\",\n"
            "  \"desired_size\": \"8\",\n"
            "  \"is_damaged\": true,\n"
            "  \"purchase_date\": \"2026-08-28T00:00:00Z\",\n"
            "  \"original_price\": 5000,\n"
            "  \"calculated_fee\": 1000,\n"
            "  \"shipping_cost\": 500,\n"
            "  \"total_amount\": 1500,\n"
            "  \"currency\": \"usd\",\n"
            "  \"is_within_free_window\": true,\n"
            "  \"payment_status\": \"pending\",\n"
            "  \"stripe_session_id\": \"cs_test_a1b2c3\",\n"
            "  \"stripe_checkout_url\": \"https://checkout.stripe.com/c/pay/cs_test_a1b2c3\",\n"
            "  \"status\": \"payment_pending\",\n"
            "  \"user_tracking_number\": null,\n"
            "  \"replacement_tracking_number\": null,\n"
            "  \"notes\": null,\n"
            "  \"created_at\": \"2026-09-01T12:00:00Z\",\n"
            "  \"updated_at\": \"2026-09-01T12:00:00Z\"\n"
            "}\n"
            "```"
        ),
        request=RingExchangeRequestCreateSerializer,
        responses=RingExchangeRequestSerializer,
    )
    def post(self, request):
        import stripe
        serializer = RingExchangeRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        policy = RingExchangePolicy.get_policy()
        is_damaged = data["is_damaged"]

        # Verify WooCommerce order ownership & auto-populate purchase_date and original_price
        wc = get_wc_api()
        wc_order = None
        if wc:
            orders_helper = CurrentUserOrdersAPIView()
            user_orders = orders_helper._fetch_orders_for_email(wc, request.user.email)
            for o in user_orders:
                if str(o.get("id")) == str(data["order_id"]):
                    wc_order = o
                    break

            if not wc_order and user_orders:
                return Response(
                    {"detail": f"Order #{data['order_id']} was not found under your account."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if wc_order:
            from django.utils.dateparse import parse_datetime
            date_str = wc_order.get("date_created")
            parsed_dt = parse_datetime(date_str) if date_str else None
            purchase_date = parsed_dt or data.get("purchase_date") or timezone.now()

            line_items = wc_order.get("line_items") or []
            item_price = 0.0
            for li in line_items:
                if data["original_item_name"].strip().lower() in (li.get("name") or "").strip().lower():
                    item_price = float(li.get("price") or li.get("total") or 0)
                    break
            if item_price == 0.0 and line_items:
                item_price = float(line_items[0].get("price") or line_items[0].get("total") or 0)

            original_price = item_price if item_price > 0 else (data.get("original_price") or 0.0)
        else:
            purchase_date = data.get("purchase_date") or timezone.now()
            original_price = data.get("original_price") or 0.0

        if purchase_date and timezone.is_naive(purchase_date):
            purchase_date = timezone.make_aware(purchase_date, timezone.get_current_timezone())

        fee_calc = RingExchangeRequest.calculate_exchange_fee(
            policy=policy,
            purchase_date=purchase_date,
            is_damaged=is_damaged,
            original_price_cents=original_price,
        )

        stripe_session_id = None
        stripe_url = None
        payment_status = RingExchangeRequest.PAYMENT_NOT_REQUIRED
        initial_status = RingExchangeRequest.STATUS_APPROVED

        if not fee_calc["is_free"]:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            if not stripe.api_key:
                return Response(
                    {"detail": "Stripe payment service is not configured."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            success_url = data.get("success_url") or "https://example.com/exchange/success"
            cancel_url = data.get("cancel_url") or "https://example.com/exchange/cancel"

            line_items = []
            if fee_calc["fee"] > 0:
                line_items.append({
                    "price_data": {
                        "currency": policy.currency,
                        "product_data": {
                            "name": f"Ring Exchange Fee ({data['original_item_name']})",
                        },
                        "unit_amount": fee_calc["fee"],
                    },
                    "quantity": 1,
                })
            if fee_calc["shipping"] > 0:
                line_items.append({
                    "price_data": {
                        "currency": policy.currency,
                        "product_data": {
                            "name": "Exchange Shipping Fee",
                        },
                        "unit_amount": fee_calc["shipping"],
                    },
                    "quantity": 1,
                })

            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=line_items,
                    mode="payment",
                    success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=cancel_url,
                    client_reference_id=str(request.user.id),
                    metadata={
                        "type": "ring_exchange",
                        "user_id": str(request.user.id),
                        "order_id": str(data["order_id"]),
                    },
                )
                stripe_session_id = session.id
                stripe_url = session.url
                payment_status = RingExchangeRequest.PAYMENT_PENDING
                initial_status = RingExchangeRequest.STATUS_PAYMENT_PENDING
            except Exception as exc:
                return Response(
                    {"detail": f"Stripe error: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        exchange_request = RingExchangeRequest.objects.create(
            user=request.user,
            order_id=data["order_id"],
            original_item_name=data["original_item_name"],
            original_size=data["original_size"],
            desired_size=data["desired_size"],
            is_damaged=is_damaged,
            purchase_date=purchase_date,
            original_price=original_price,
            calculated_fee=fee_calc["fee"],
            shipping_cost=fee_calc["shipping"],
            total_amount=fee_calc["total"],
            currency=policy.currency,
            is_within_free_window=fee_calc["within_free_window"],
            payment_status=payment_status,
            stripe_session_id=stripe_session_id,
            status=initial_status,
        )

        res_serializer = RingExchangeRequestSerializer(exchange_request)
        response_data = res_serializer.data
        if stripe_url:
            response_data["stripe_checkout_url"] = stripe_url

        return Response(response_data, status=status.HTTP_201_CREATED)


class RingExchangeDetailAPIView(APIView):
    """
    GET /api/auth/ring-exchange/<id>/
    Retrieve single ring exchange request details.

    PATCH /api/auth/ring-exchange/<id>/
    Update return shipment tracking number.

    Request Example (PATCH):
    {
        "user_tracking_number": "1Z9999999999999999"
    }

    Response Example (200 OK):
    {
        "id": 1,
        "order_id": "1001",
        "original_item_name": "Amore Silver Ring",
        "original_size": "7",
        "desired_size": "8",
        "status": "user_shipped",
        "user_tracking_number": "1Z9999999999999999",
        "replacement_tracking_number": null,
        "created_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-01T12:10:00Z"
    }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[RING_EXCHANGE_TAG],
        summary="Get ring exchange request details",
        description=(
            "Returns details for a specific ring exchange request.\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "{\n"
            "  \"id\": 1,\n"
            "  \"order_id\": \"1001\",\n"
            "  \"original_item_name\": \"Amore Silver Ring\",\n"
            "  \"original_size\": \"7\",\n"
            "  \"desired_size\": \"8\",\n"
            "  \"is_damaged\": false,\n"
            "  \"status\": \"approved\"\n"
            "}\n"
            "```"
        ),
        responses=RingExchangeRequestSerializer,
    )
    def get(self, request, pk):
        try:
            exchange = RingExchangeRequest.objects.get(pk=pk, user=request.user)
        except RingExchangeRequest.DoesNotExist:
            return Response(
                {"detail": "Ring exchange request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = RingExchangeRequestSerializer(exchange)
        return Response(serializer.data)

    @extend_schema(
        tags=[RING_EXCHANGE_TAG],
        summary="Update return shipment tracking number",
        description=(
            "Allows the user to attach their return tracking number once they ship the original ring back.\n\n"
            "**Request Example**:\n"
            "```json\n"
            "{\n"
            "  \"user_tracking_number\": \"1Z9999999999999999\"\n"
            "}\n"
            "```\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "{\n"
            "  \"id\": 1,\n"
            "  \"status\": \"user_shipped\",\n"
            "  \"user_tracking_number\": \"1Z9999999999999999\"\n"
            "}\n"
            "```"
        ),
        request=RingExchangeTrackingUpdateSerializer,
        responses=RingExchangeRequestSerializer,
    )
    def patch(self, request, pk):
        try:
            exchange = RingExchangeRequest.objects.get(pk=pk, user=request.user)
        except RingExchangeRequest.DoesNotExist:
            return Response(
                {"detail": "Ring exchange request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RingExchangeTrackingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exchange.user_tracking_number = serializer.validated_data["user_tracking_number"]
        if exchange.status in [RingExchangeRequest.STATUS_APPROVED, RingExchangeRequest.STATUS_PENDING]:
            exchange.status = RingExchangeRequest.STATUS_USER_SHIPPED
        exchange.save(update_fields=["user_tracking_number", "status", "updated_at"])

        res_serializer = RingExchangeRequestSerializer(exchange)
        return Response(res_serializer.data)


class RingExchangeStripeWebhookAPIView(APIView):
    """
    POST /api/auth/ring-exchange/webhook/

    Processes Stripe webhook events for ring exchange payments.

    Response Example (200 OK):
    {
        "detail": "ok"
    }
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=[RING_EXCHANGE_TAG],
        summary="Ring Exchange Stripe webhook callback",
        description="Processes Stripe webhook events for ring exchange payments.",
        request=None,
        responses=None,
    )
    def post(self, request):
        import stripe
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
            session_id = data_object.get("id")
            payment_intent = data_object.get("payment_intent")
            if not session_id:
                return Response({"detail": "Missing session id."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                exchange = RingExchangeRequest.objects.get(stripe_session_id=session_id)
            except RingExchangeRequest.DoesNotExist:
                return Response({"detail": "Not a ring exchange session."}, status=status.HTTP_200_OK)

            if exchange.payment_status == RingExchangeRequest.PAYMENT_PAID:
                return Response({"detail": "Already completed."}, status=status.HTTP_200_OK)

            exchange.payment_status = RingExchangeRequest.PAYMENT_PAID
            exchange.status = RingExchangeRequest.STATUS_APPROVED
            exchange.stripe_payment_intent_id = payment_intent
            exchange.save(update_fields=["payment_status", "status", "stripe_payment_intent_id", "updated_at"])

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)


REFUND_TAG = "Refund"


def get_user_ring_purchase_date(user, order_id=None):
    """
    Fetch the purchase date of the given authenticated user's ring purchase.
    1. Checks WooCommerce API for user's orders if WooCommerce is configured.
       - If order_id is provided, looks for that specific order.
       - Otherwise, looks for orders and selects the most recent order.
    2. If WooCommerce is not connected or no WooCommerce order found,
       checks RefundRequest and RingExchangeRequest in DB for the user.
    Returns timezone-aware datetime object or None if no purchase date found.
    """
    if not user or not user.is_authenticated:
        return None

    def _ensure_aware(dt):
        if dt and timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    wc = get_wc_api()
    if wc:
        try:
            orders_helper = CurrentUserOrdersAPIView()
            user_orders = orders_helper._fetch_orders_for_email(wc, user.email)
            if user_orders:
                selected_order = None
                if order_id:
                    for o in user_orders:
                        if str(o.get("id")) == str(order_id):
                            selected_order = o
                            break
                if not selected_order:
                    selected_order = user_orders[0]

                if selected_order:
                    date_str = selected_order.get("date_created")
                    if date_str:
                        from django.utils.dateparse import parse_datetime
                        parsed_dt = parse_datetime(date_str)
                        if parsed_dt:
                            return _ensure_aware(parsed_dt)
        except Exception:
            pass

    ref_req = RefundRequest.objects.filter(user=user).exclude(purchase_date__isnull=True).order_by("-purchase_date").first()
    ex_req = RingExchangeRequest.objects.filter(user=user).exclude(purchase_date__isnull=True).order_by("-purchase_date").first()

    dates = []
    if ref_req and ref_req.purchase_date:
        dates.append(_ensure_aware(ref_req.purchase_date))
    if ex_req and ex_req.purchase_date:
        dates.append(_ensure_aware(ex_req.purchase_date))

    if dates:
        return max(dates)

    return None


class RefundPolicyAPIView(APIView):
    """
    GET /api/auth/refund/policy/

    Return active refund policy configuration (21-day deadline window, return shipping address, instructions)
    and user's calculated refund deadline date.

    Response Example (200 OK):
    {
        "refund_deadline_days": 21,
        "return_shipping_address": "Amore Rings Returns Dept.\n123 Luxury Lane, Suite 100\nNew York, NY 10001, USA",
        "instructions": "To return your ring for a refund, please package the item securely...",
        "restocking_fee_percentage": "0.00",
        "currency": "usd",
        "updated_at": "2026-09-01T12:00:00Z",
        "user_purchase_date": "2026-08-20T10:00:00Z",
        "user_refund_deadline": "2026-09-10T10:00:00Z",
        "refund_deadline_date": "2026-09-10T10:00:00Z",
        "return_deadline": "2026-09-10T10:00:00Z",
        "is_eligible": true
    }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[REFUND_TAG],
        summary="Get active refund policy",
        description=(
            "Returns the active refund policy details including return deadline window (default 21 days), "
            "return shipping address, instructions, and user's calculated refund deadline date.\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "{\n"
            "  \"refund_deadline_days\": 21,\n"
            "  \"return_shipping_address\": \"Amore Rings Returns Dept.\\n123 Luxury Lane, Suite 100\\nNew York, NY 10001, USA\",\n"
            "  \"instructions\": \"To return your ring for a refund, please package the item securely in its original box and ship it to our returns department.\",\n"
            "  \"restocking_fee_percentage\": \"0.00\",\n"
            "  \"currency\": \"usd\",\n"
            "  \"updated_at\": \"2026-09-01T12:00:00Z\",\n"
            "  \"user_purchase_date\": \"2026-08-20T10:00:00Z\",\n"
            "  \"user_refund_deadline\": \"2026-09-10T10:00:00Z\",\n"
            "  \"refund_deadline_date\": \"2026-09-10T10:00:00Z\",\n"
            "  \"return_deadline\": \"2026-09-10T10:00:00Z\",\n"
            "  \"is_eligible\": true\n"
            "}\n"
            "```"
        ),
        responses=RefundPolicySerializer,
    )
    def get(self, request):
        policy = RefundPolicy.get_policy()
        serializer = RefundPolicySerializer(policy, context={'request': request})
        return Response(serializer.data)


class RefundAPIView(APIView):
    """
    GET /api/auth/refund/
    List all refund requests for the authenticated user.

    POST /api/auth/refund/
    Submit a new refund request. Auto-verifies WooCommerce order ownership & 21-day return deadline.

    Request Example:
    {
        "order_id": "1001",
        "item_name": "Amore Silver Ring",
        "item_size": "7",
        "reason": "Size didn't fit as expected",
        "purchase_date": "2026-08-25T00:00:00Z",
        "original_price": 5000
    }

    Response Example (201 Created):
    {
        "id": 1,
        "order_id": "1001",
        "item_name": "Amore Silver Ring",
        "item_size": "7",
        "reason": "Size didn't fit as expected",
        "purchase_date": "2026-08-25T00:00:00Z",
        "original_price": 5000,
        "refund_amount": 5000,
        "currency": "usd",
        "return_deadline": "2026-09-15T00:00:00Z",
        "is_eligible": true,
        "user_tracking_number": null,
        "status": "requested",
        "notes": null,
        "created_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-01T12:00:00Z"
    }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[REFUND_TAG],
        summary="List my refund requests",
        description=(
            "Returns all refund requests submitted by the authenticated user.\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"id\": 1,\n"
            "    \"order_id\": \"1001\",\n"
            "    \"item_name\": \"Amore Silver Ring\",\n"
            "    \"item_size\": \"7\",\n"
            "    \"reason\": \"Size didn't fit as expected\",\n"
            "    \"purchase_date\": \"2026-08-25T00:00:00Z\",\n"
            "    \"original_price\": 5000,\n"
            "    \"refund_amount\": 5000,\n"
            "    \"currency\": \"usd\",\n"
            "    \"return_deadline\": \"2026-09-15T00:00:00Z\",\n"
            "    \"is_eligible\": true,\n"
            "    \"user_tracking_number\": null,\n"
            "    \"status\": \"requested\",\n"
            "    \"notes\": null,\n"
            "    \"created_at\": \"2026-09-01T12:00:00Z\",\n"
            "    \"updated_at\": \"2026-09-01T12:00:00Z\"\n"
            "  }\n"
            "]\n"
            "```"
        ),
        responses=RefundRequestSerializer(many=True),
    )
    def get(self, request):
        requests = RefundRequest.objects.filter(user=request.user)
        serializer = RefundRequestSerializer(requests, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=[REFUND_TAG],
        summary="Submit a refund request",
        description=(
            "Submits a request for a refund on a purchased item. "
            "Auto-verifies WooCommerce order ownership and calculates deadline eligibility (21 days default).\n\n"
            "**Request Example**:\n"
            "```json\n"
            "{\n"
            "  \"order_id\": \"1001\",\n"
            "  \"item_name\": \"Amore Silver Ring\",\n"
            "  \"item_size\": \"7\",\n"
            "  \"reason\": \"Item changed mind\",\n"
            "  \"purchase_date\": \"2026-08-25T00:00:00Z\",\n"
            "  \"original_price\": 5000\n"
            "}\n"
            "```\n\n"
            "**Response Example (201 Created)**:\n"
            "```json\n"
            "{\n"
            "  \"id\": 1,\n"
            "  \"order_id\": \"1001\",\n"
            "  \"item_name\": \"Amore Silver Ring\",\n"
            "  \"item_size\": \"7\",\n"
            "  \"reason\": \"Item changed mind\",\n"
            "  \"purchase_date\": \"2026-08-25T00:00:00Z\",\n"
            "  \"original_price\": 5000,\n"
            "  \"refund_amount\": 5000,\n"
            "  \"currency\": \"usd\",\n"
            "  \"return_deadline\": \"2026-09-15T00:00:00Z\",\n"
            "  \"is_eligible\": true,\n"
            "  \"user_tracking_number\": null,\n"
            "  \"status\": \"requested\",\n"
            "  \"notes\": null,\n"
            "  \"created_at\": \"2026-09-01T12:00:00Z\",\n"
            "  \"updated_at\": \"2026-09-01T12:00:00Z\"\n"
            "}\n"
            "```"
        ),
        request=RefundRequestCreateSerializer,
        responses=RefundRequestSerializer,
    )
    def post(self, request):
        serializer = RefundRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        policy = RefundPolicy.get_policy()

        # Verify WooCommerce order ownership & auto-populate purchase_date and original_price
        wc = get_wc_api()
        wc_order = None
        if wc:
            orders_helper = CurrentUserOrdersAPIView()
            user_orders = orders_helper._fetch_orders_for_email(wc, request.user.email)
            for o in user_orders:
                if str(o.get("id")) == str(data["order_id"]):
                    wc_order = o
                    break

            if not wc_order and user_orders:
                return Response(
                    {"detail": f"Order #{data['order_id']} was not found under your account."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if wc_order:
            from django.utils.dateparse import parse_datetime
            date_str = wc_order.get("date_created")
            parsed_dt = parse_datetime(date_str) if date_str else None
            purchase_date = parsed_dt or data.get("purchase_date") or timezone.now()

            line_items = wc_order.get("line_items") or []
            item_price = 0.0
            for li in line_items:
                if data["item_name"].strip().lower() in (li.get("name") or "").strip().lower():
                    item_price = float(li.get("price") or li.get("total") or 0)
                    break
            if item_price == 0.0 and line_items:
                item_price = float(line_items[0].get("price") or line_items[0].get("total") or 0)

            original_price = item_price if item_price > 0 else (data.get("original_price") or 0.0)
        else:
            purchase_date = data.get("purchase_date") or timezone.now()
            original_price = data.get("original_price") or 0.0

        if purchase_date and timezone.is_naive(purchase_date):
            purchase_date = timezone.make_aware(purchase_date, timezone.get_current_timezone())

        calc = RefundRequest.calculate_refund(
            policy=policy,
            purchase_date=purchase_date,
            original_price_cents=original_price,
        )

        refund_request = RefundRequest.objects.create(
            user=request.user,
            order_id=data["order_id"],
            item_name=data["item_name"],
            item_size=data.get("item_size"),
            reason=data["reason"],
            purchase_date=purchase_date,
            original_price=original_price,
            refund_amount=calc["refund_amount"],
            currency=policy.currency,
            return_deadline=calc["return_deadline"],
            is_eligible=calc["is_eligible"],
            status=RefundRequest.STATUS_REQUESTED,
        )

        res_serializer = RefundRequestSerializer(refund_request)
        return Response(res_serializer.data, status=status.HTTP_201_CREATED)


class RefundDetailAPIView(APIView):
    """
    GET /api/auth/refund/<id>/
    Retrieve refund request details.

    PATCH /api/auth/refund/<id>/
    Update return shipment tracking number.

    Request Example (PATCH):
    {
        "user_tracking_number": "1Z9999999999999999"
    }

    Response Example (200 OK):
    {
        "id": 1,
        "order_id": "1001",
        "item_name": "Amore Silver Ring",
        "status": "ring_shipped",
        "user_tracking_number": "1Z9999999999999999",
        "updated_at": "2026-09-01T12:10:00Z"
    }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[REFUND_TAG],
        summary="Get refund request details",
        description=(
            "Returns details for a specific refund request.\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "{\n"
            "  \"id\": 1,\n"
            "  \"order_id\": \"1001\",\n"
            "  \"item_name\": \"Amore Silver Ring\",\n"
            "  \"refund_amount\": 5000,\n"
            "  \"is_eligible\": true,\n"
            "  \"status\": \"requested\"\n"
            "}\n"
            "```"
        ),
        responses=RefundRequestSerializer,
    )
    def get(self, request, pk):
        try:
            refund = RefundRequest.objects.get(pk=pk, user=request.user)
        except RefundRequest.DoesNotExist:
            return Response(
                {"detail": "Refund request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = RefundRequestSerializer(refund)
        return Response(serializer.data)

    @extend_schema(
        tags=[REFUND_TAG],
        summary="Update return shipment tracking number",
        description=(
            "Allows the user to attach their return shipment tracking number once they ship the ring back.\n\n"
            "**Request Example**:\n"
            "```json\n"
            "{\n"
            "  \"user_tracking_number\": \"1Z9999999999999999\"\n"
            "}\n"
            "```\n\n"
            "**Response Example (200 OK)**:\n"
            "```json\n"
            "{\n"
            "  \"id\": 1,\n"
            "  \"status\": \"ring_shipped\",\n"
            "  \"user_tracking_number\": \"1Z9999999999999999\"\n"
            "}\n"
            "```"
        ),
        request=RefundTrackingUpdateSerializer,
        responses=RefundRequestSerializer,
    )
    def patch(self, request, pk):
        try:
            refund = RefundRequest.objects.get(pk=pk, user=request.user)
        except RefundRequest.DoesNotExist:
            return Response(
                {"detail": "Refund request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RefundTrackingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund.user_tracking_number = serializer.validated_data["user_tracking_number"]
        if refund.status in [RefundRequest.STATUS_REQUESTED]:
            refund.status = RefundRequest.STATUS_RING_SHIPPED
        refund.save(update_fields=["user_tracking_number", "status", "updated_at"])

        res_serializer = RefundRequestSerializer(refund)
        return Response(res_serializer.data)



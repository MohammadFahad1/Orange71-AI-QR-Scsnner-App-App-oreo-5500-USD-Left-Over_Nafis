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
)
from .woocommerce_client import get_wc_api
from .order_serializers import OrderSerializer, SimpleOrderSerializer
from .utils import fetch_users

User = get_user_model()
from .models import AmbassadorBooking, AmbassadorSlot, SpeacialEvent, Support

OTP_EXPIRY_MINUTES = 10
AUTH_TAG = "Authentication"
TOKEN_TAG = "Tokens"
PROFILE_TAG = "Profile"
SPECIAL_EVENT_TAG = "Special Event"
SUPPORT_TAG = "Support"


def generate_otp():
    return f"{secrets.randbelow(10000):04d}"


def send_otp_email(user, otp):
    send_mail(
        subject="Amore Rings verification code",
        message=(
            f"Your Amore Rings verification code is {otp}. "
            f"It expires in {OTP_EXPIRY_MINUTES} minutes."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
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
    """Return the current user's WooCommerce orders and their items."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Membership Status"],
        summary="Get membership status",
        description="Returns the authenticated user membership status from the configured WooCommerce store.",
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

        # Normalize response into our serializer format
        normalized = []
        for o in orders:
            order_sizes = []
            normalized.append({
                "id": o.get("id"),
                "status": o.get("status"),
                "total": o.get("total"),
                "currency": o.get("currency"),
                "date_created": o.get("date_created"),
                "sizes": order_sizes,
                "line_items": [
                    {
                        "id": li.get("id"),
                        "name": li.get("name"),
                        "product_id": li.get("product_id"),
                        "quantity": li.get("quantity"),
                        "total": li.get("total"),
                    }
                    for li in o.get("line_items", [])
                ],
            })

            for line_item in normalized[-1]["line_items"]:
                item_details = line_item.get("item_details") or {}
                line_item["size"] = item_details.get("size")
                if item_details.get("size") and item_details["size"] not in order_sizes:
                    order_sizes.append(item_details["size"])

        # Simplify output: only return each item's name and size
        simplified = []
        for o in normalized:
            items = []
            for li in o.get("line_items", []):
                items.append({
                    "name": li.get("name"),
                    "size": li.get("size"),
                })
            simplified.append({
                "id": o.get("id"),
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

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Conversation, CreditBalance, Block, UserConnection, CreditPackage, CreditPurchase
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    CreditBalanceSerializer,
    UserConnectionSerializer,
    CreditPackageSerializer,
    CreditPurchaseSerializer,
)

User = get_user_model()

CHAT_TAG = 'Chat'


class ConversationWithUserAPIView(APIView):
    """
    GET /api/chat/users/<user_id>/
    Get or create a 1-to-1 conversation with the specified user.
    Requires an active (CONNECTED) mutual QR scan connection.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Get or create conversation with a user',
        description=(
            'Returns the existing 1-to-1 conversation between the authenticated user '
            'and the target user. Requires a mutual QR scan connection to exist first.'
        ),
        responses=ConversationSerializer,
    )
    def get(self, request, user_id):
        if request.user.id == user_id:
            return Response(
                {'detail': 'You cannot start a conversation with yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Require an active mutual connection
        connection = UserConnection.get_active_connection(request.user, other_user)
        if connection is None:
            return Response(
                {'detail': 'No active connection with this user. Scan each other\'s QR code first.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation = Conversation.get_or_create_between(request.user, other_user)
        serializer = ConversationSerializer(conversation, context={'request': request})
        return Response(serializer.data)


class ConversationListAPIView(APIView):
    """
    GET /api/chat/conversations/
    List all conversations the authenticated user is part of.
    Optionally filter by the other participant's name with ?q=<name>.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='List my conversations',
        description=(
            'Returns all conversations the authenticated user is a participant in, '
            'ordered by most recent. Pass an optional ?q= to filter by the other '
            'participant\'s name (case-insensitive, partial match).'
        ),
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter conversations by the other participant's name.",
            ),
        ],
        responses=ConversationSerializer(many=True),
    )
    def get(self, request):
        query = request.query_params.get('q', '').strip()

        if query:
            # Query the M2M through table directly to find conversation IDs where
            # a participant other than the requester has a matching name.
            through = Conversation.participants.through
            matching_conv_ids = (
                through.objects
                .filter(user__name__icontains=query)
                .exclude(user_id=request.user.id)
                .values_list('conversation_id', flat=True)
            )
            conversations = request.user.conversations.filter(id__in=matching_conv_ids)
        else:
            conversations = request.user.conversations

        conversations = (
            conversations
            .prefetch_related('participants', 'messages')
            .distinct()
            .order_by('-created_at')
        )

        serializer = ConversationSerializer(
            conversations, many=True, context={'request': request}
        )
        return Response(serializer.data)


class MessageHistoryAPIView(APIView):
    """
    GET /api/chat/conversations/<conversation_id>/messages/
    Return paginated message history for a conversation.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Get message history',
        description='Returns all messages for the given conversation. User must be a participant.',
        responses=MessageSerializer(many=True),
    )
    def get(self, request, conversation_id):
        try:
            conversation = request.user.conversations.get(id=conversation_id)
        except Exception:
            return Response(
                {'detail': 'Conversation not found or you are not a participant.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = conversation.messages.select_related('sender').all()
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)


class CreditBalanceAPIView(APIView):
    """
    GET /api/chat/credits/
    Return the authenticated user's current credit balance.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Get credit balance',
        description='Returns the current credit balance for the authenticated user. New users start with 500 mock credits.',
        responses=CreditBalanceSerializer,
    )
    def get(self, request):
        balance = CreditBalance.get_or_create_for_user(request.user)
        serializer = CreditBalanceSerializer(balance)
        return Response(serializer.data)


class BlockUserAPIView(APIView):
    """
    POST   /api/chat/users/<user_id>/block/  — block a user
    DELETE /api/chat/users/<user_id>/block/  — unblock a user
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Block a user',
        description='Blocks the specified user. Neither party can send messages while the block is active.',
        responses={204: None},
    )
    def post(self, request, user_id):
        if request.user.id == user_id:
            return Response(
                {'detail': 'You cannot block yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        _, created = Block.objects.get_or_create(blocker=request.user, blocked=target)
        if not created:
            return Response(
                {'detail': 'You have already blocked this user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Unblock a user',
        description='Removes an existing block. Messaging between both parties resumes.',
        responses={204: None},
    )
    def delete(self, request, user_id):
        deleted, _ = Block.objects.filter(
            blocker=request.user, blocked_id=user_id
        ).delete()
        if not deleted:
            return Response(
                {'detail': 'You have not blocked this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScanQRAPIView(APIView):
    """
    POST /api/chat/scan/<slug>/

    Called when the authenticated user scans another user's QR code.
    The QR encodes the target user's slug.

    Logic:
    - If the target already scanned me (pending connection exists with target=initiator, me=receiver)
      → mark CONNECTED, create the conversation.
    - If I already scanned the target before → return the existing pending status (idempotent).
    - Otherwise → create a new PENDING connection.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Scan a user QR code',
        description=(
            'Records that the authenticated user scanned the target user\'s QR code. '
            'If the target has already scanned back, the connection becomes CONNECTED '
            'and a conversation is created. Otherwise it stays PENDING.'
        ),
        responses=UserConnectionSerializer,
    )
    def post(self, request, slug):
        scanner = request.user

        try:
            target = User.objects.get(slug=slug)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if target == scanner:
            return Response(
                {'detail': 'You cannot scan your own QR code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if target already scanned me → complete the handshake
        reverse = UserConnection.objects.filter(
            initiator=target,
            receiver=scanner,
            status=UserConnection.STATUS_PENDING,
        ).first()

        if reverse:
            conversation = Conversation.get_or_create_between(scanner, target)
            reverse.status = UserConnection.STATUS_CONNECTED
            reverse.conversation = conversation
            reverse.connected_at = timezone.now()
            reverse.save(update_fields=['status', 'conversation', 'connected_at'])
            serializer = UserConnectionSerializer(reverse, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Check if I already scanned this person (idempotent)
        existing = UserConnection.objects.filter(
            initiator=scanner,
            receiver=target,
        ).first()

        if existing:
            serializer = UserConnectionSerializer(existing, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        # First scan — create pending connection
        connection = UserConnection.objects.create(
            initiator=scanner,
            receiver=target,
            status=UserConnection.STATUS_PENDING,
        )
        serializer = UserConnectionSerializer(connection, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConnectionListAPIView(APIView):
    """
    GET /api/chat/connections/
    Returns all CONNECTED connections for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='List my connections',
        description='Returns all users the authenticated user has a confirmed mutual QR scan connection with.',
        responses=UserConnectionSerializer(many=True),
    )
    def get(self, request):
        from django.db.models import Q
        connections = UserConnection.objects.filter(
            Q(initiator=request.user) | Q(receiver=request.user),
            status=UserConnection.STATUS_CONNECTED,
        ).select_related('initiator', 'receiver', 'conversation')

        serializer = UserConnectionSerializer(connections, many=True, context={'request': request})
        return Response(serializer.data)


class CreditPackageListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='List credit packages',
        description='Returns all active credit packages available for purchase.',
        responses=CreditPackageSerializer(many=True),
    )
    def get(self, request):
        packages = CreditPackage.objects.filter(is_active=True)
        serializer = CreditPackageSerializer(packages, many=True)
        return Response(serializer.data)


class CreditPurchaseCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Purchase a credit package',
        description='Creates a Stripe Checkout Session for the selected credit package. Returns the session URL for the mobile app to open.',
        request=serializers.Serializer,
        responses=CreditPurchaseSerializer,
    )
    def post(self, request):
        from django.conf import settings
        import stripe
        from .serializers import CreditPackageSerializer

        package_id = request.data.get('package_id')
        if package_id is None:
            return Response({'detail': 'package_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            package = CreditPackage.objects.get(pk=package_id, is_active=True)
        except CreditPackage.DoesNotExist:
            return Response({'detail': 'Package not found or inactive.'}, status=status.HTTP_404_NOT_FOUND)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        if not stripe.api_key:
            return Response({'detail': 'Stripe is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        success_url = request.data.get('success_url') or 'https://example.com/success'
        cancel_url = request.data.get('cancel_url') or 'https://example.com/cancel'

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': package.currency,
                            'product_data': {
                                'name': package.name,
                            },
                            'unit_amount': package.price,
                        },
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                client_reference_id=str(request.user.id),
                metadata={
                    'package_id': str(package.id),
                    'user_id': str(request.user.id),
                },
            )
        except Exception as exc:
            return Response({'detail': f'Stripe error: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)

        purchase = CreditPurchase.objects.create(
            user=request.user,
            package=package,
            stripe_session_id=session.id,
            credits_amount=package.credits_amount,
            amount_paid=package.price,
            currency=package.currency,
        )

        serializer = CreditPurchaseSerializer(purchase, context={'request': request})
        return Response({
            'session_id': session.id,
            'url': session.url,
            'purchase': serializer.data,
        }, status=status.HTTP_201_CREATED)


class CreditPurchaseHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Get credit purchase history',
        description='Returns the authenticated user credit purchase history.',
        responses=CreditPurchaseSerializer(many=True),
    )
    def get(self, request):
        purchases = CreditPurchase.objects.filter(user=request.user)
        serializer = CreditPurchaseSerializer(purchases, many=True, context={'request': request})
        return Response(serializer.data)


class StripeWebhookAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Stripe webhook',
        description='Handles Stripe webhook events to confirm credit purchases.',
        request=None,
        responses=None,
    )
    def post(self, request):
        from django.conf import settings
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not webhook_secret:
            return Response({'detail': 'Webhook secret not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=webhook_secret)
        except ValueError:
            return Response({'detail': 'Invalid payload.'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get('type')
        data_object = event.get('data', {}).get('object', {})

        if event_type == 'checkout.session.completed':
            session_id = data_object.get('id')
            payment_intent = data_object.get('payment_intent')
            if not session_id:
                return Response({'detail': 'Missing session id.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                purchase = CreditPurchase.objects.select_related('user', 'package').get(stripe_session_id=session_id)
            except CreditPurchase.DoesNotExist:
                return Response({'detail': 'Purchase not found.'}, status=status.HTTP_404_NOT_FOUND)

            if purchase.status == CreditPurchase.STATUS_COMPLETED:
                return Response({'detail': 'Already completed.'}, status=status.HTTP_200_OK)

            purchase.status = CreditPurchase.STATUS_COMPLETED
            purchase.stripe_payment_intent_id = payment_intent
            purchase.completed_at = timezone.now()
            purchase.save(update_fields=['status', 'stripe_payment_intent_id', 'completed_at'])

            if purchase.user and purchase.package:
                balance = CreditBalance.get_or_create_for_user(purchase.user)
                balance.add(purchase.credits_amount)

        return Response({'detail': 'ok'}, status=status.HTTP_200_OK)


class StripeSuccessAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Stripe success redirect',
        description='Simple success page shown after Stripe payment.',
        responses=None,
    )
    def get(self, request):
        return Response({'detail': 'Payment successful. Credits will be added shortly.'}, status=status.HTTP_200_OK)


class StripeCancelAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=[CHAT_TAG],
        summary='Stripe cancel redirect',
        description='Simple cancel page shown when Stripe payment is cancelled.',
        responses=None,
    )
    def get(self, request):
        return Response({'detail': 'Payment cancelled.'}, status=status.HTTP_200_OK)

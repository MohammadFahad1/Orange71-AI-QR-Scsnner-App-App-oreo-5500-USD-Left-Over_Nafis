from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """A 1-to-1 conversation between two users."""

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        ids = list(self.participants.values_list("id", flat=True))
        return f"Conversation({ids})"

    @classmethod
    def get_or_create_between(cls, user_a, user_b):
        """Return the existing 1-to-1 conversation between two users, or create one."""
        conversation = (
            cls.objects.filter(participants=user_a).filter(participants=user_b).first()
        )
        if conversation is None:
            conversation = cls.objects.create()
            conversation.participants.add(user_a, user_b)
        return conversation


class Message(models.Model):
    """A single text message inside a conversation."""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message({self.sender_id} → conv {self.conversation_id})"


class CreditBalance(models.Model):
    """Credit balance for a user. 1 credit = 1 sent message."""

    MOCK_STARTING_CREDITS = 100

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="credit_balance",
    )
    balance = models.PositiveIntegerField(default=MOCK_STARTING_CREDITS)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CreditBalance(user={self.user_id}, balance={self.balance})"

    @classmethod
    def get_or_create_for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    def deduct(self, amount=1):
        """Deduct credits. Returns True on success, False if insufficient."""
        if self.balance < amount:
            return False
        self.balance -= amount
        self.save(update_fields=["balance", "updated_at"])
        return True

    def add(self, amount):
        self.balance += amount
        self.save(update_fields=["balance", "updated_at"])


class CreditPackage(models.Model):
    """Admin-defined credit purchase package."""

    name = models.CharField(max_length=120)
    credits_amount = models.PositiveIntegerField()
    price = models.PositiveIntegerField(help_text='Price in the smallest currency unit (e.g. cents).')
    currency = models.CharField(max_length=10, default='usd')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f'{self.name} - {self.credits_amount} credits ({self.price}/{self.currency})'


class CreditPurchase(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='credit_purchases')
    package = models.ForeignKey(CreditPackage, on_delete=models.PROTECT, related_name='purchases')
    stripe_session_id = models.CharField(max_length=255, unique=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    credits_amount = models.PositiveIntegerField()
    amount_paid = models.PositiveIntegerField(help_text='Amount paid in smallest currency unit.')
    currency = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} -> {self.package} ({self.status})'


class Block(models.Model):
    """Records that `blocker` has blocked `blocked`."""

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocking",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("blocker", "blocked")

    def __str__(self):
        return f"Block({self.blocker_id} → {self.blocked_id})"


class UserConnection(models.Model):
    """
    Tracks the mutual QR scan handshake between two users.

    Flow:
      - User A scans User B's QR → record created: initiator=A, receiver=B, status=PENDING
      - User B scans User A's QR → status upgraded to CONNECTED, conversation created
    """

    STATUS_PENDING = "pending"
    STATUS_CONNECTED = "connected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONNECTED, "Connected"),
    ]

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="initiated_connections",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_connections",
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="connection",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    connected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Only one pending/connected record per ordered pair
        unique_together = ("initiator", "receiver")

    def __str__(self):
        return (
            f"UserConnection({self.initiator_id} → {self.receiver_id}, {self.status})"
        )

    @classmethod
    def get_active_connection(cls, user_a, user_b):
        """Return a CONNECTED connection between two users regardless of direction."""
        return (
            cls.objects
            .filter(
                status=cls.STATUS_CONNECTED,
            )
            .filter(
                models.Q(initiator=user_a, receiver=user_b)
                | models.Q(initiator=user_b, receiver=user_a)
            )
            .first()
        )

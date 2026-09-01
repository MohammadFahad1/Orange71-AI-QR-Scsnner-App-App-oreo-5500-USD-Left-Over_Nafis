import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from .models import Conversation, Message, CreditBalance, Block

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single conversation.

    URL: ws://<host>/ws/chat/<conversation_id>/
    Auth: JWT must be passed as ?token=<access_token> query param,
          handled by the JwtAuthMiddleware wrapping this consumer.
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if self.user is None or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = f'chat_{self.conversation_id}'

        # Verify the user is actually a participant
        is_participant = await self._is_participant(self.user, self.conversation_id)
        if not is_participant:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error('Invalid JSON.')
            return

        message_type = data.get('type')

        if message_type == 'chat_message':
            content = (data.get('content') or '').strip()
            if not content:
                await self._send_error('Message content cannot be empty.')
                return

            # Reject if either party has blocked the other
            is_blocked = await self._is_blocked(self.user, self.conversation_id)
            if is_blocked:
                await self._send_error('Messaging is blocked in this conversation.')
                return

            # Deduct credit before saving
            deducted = await self._deduct_credit(self.user)
            if not deducted:
                await self._send_error('Insufficient credits.')
                return

            # Persist message
            message = await self._save_message(self.user, self.conversation_id, content)

            event = {
                'type': 'broadcast_message',
                'message_id': message.id,
                'conversation_id': int(self.conversation_id),
                'sender_id': self.user.id,
                'sender_name': self.user.name,
                'content': content,
                'created_at': message.created_at.isoformat(),
            }

            # 1. Broadcast to conversation group (both participants' chat screens)
            await self.channel_layer.group_send(self.group_name, event)

            # 2. Push an inbox update to every participant's personal group
            #    so their conversation list updates in real time.
            participant_ids = await self._get_participant_ids(self.conversation_id)
            for uid in participant_ids:
                await self.channel_layer.group_send(
                    f'inbox_{uid}',
                    {
                        'type': 'inbox_update',
                        'conversation_id': int(self.conversation_id),
                        'sender_id': self.user.id,
                        'sender_name': self.user.name,
                        'content': content,
                        'created_at': message.created_at.isoformat(),
                    },
                )
        else:
            await self._send_error(f'Unknown message type: {message_type!r}')

    async def broadcast_message(self, event):
        """Handler called by group_send — forwards the message to this WebSocket."""
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'chat_message',
                    'message_id': event['message_id'],
                    'conversation_id': event['conversation_id'],
                    'sender_id': event['sender_id'],
                    'sender_name': event['sender_name'],
                    'content': event['content'],
                    'created_at': event['created_at'],
                }
            )
        )

    async def _send_error(self, detail):
        await self.send(text_data=json.dumps({'type': 'error', 'detail': detail}))

    # ------------------------------------------------------------------ #
    # Database helpers (sync → async bridge)
    # ------------------------------------------------------------------ #

    @database_sync_to_async
    def _is_participant(self, user, conversation_id):
        return Conversation.objects.filter(
            id=conversation_id, participants=user
        ).exists()

    @database_sync_to_async
    def _is_blocked(self, user, conversation_id):
        """Return True if a block exists in either direction between the two participants."""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return False
        other = conversation.participants.exclude(id=user.id).first()
        if other is None:
            return False
        return Block.objects.filter(
            blocker__in=[user, other],
            blocked__in=[user, other],
        ).exists()

    @database_sync_to_async
    def _deduct_credit(self, user):
        balance = CreditBalance.get_or_create_for_user(user)
        return balance.deduct(1)

    @database_sync_to_async
    def _save_message(self, user, conversation_id, content):
        return Message.objects.create(
            conversation_id=conversation_id,
            sender=user,
            content=content,
        )

    @database_sync_to_async
    def _get_participant_ids(self, conversation_id):
        return list(
            Conversation.objects.get(id=conversation_id)
            .participants.values_list('id', flat=True)
        )


class InboxConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for the conversation list / inbox screen.

    URL: ws://<host>/ws/inbox/
    Auth: JWT via ?token=<access_token>

    Receives a push event whenever any conversation the user is part of
    gets a new message, so the list (last message, unread indicator) can
    update in real time without polling.

    Incoming event shape (server → client):
    {
        "type": "inbox_update",
        "conversation_id": 5,
        "sender_id": 12,
        "sender_name": "Jane",
        "content": "Hey!",
        "created_at": "2026-07-16T11:00:00+00:00"
    }
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if self.user is None or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f'inbox_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def inbox_update(self, event):
        """Receive an inbox update pushed by ChatConsumer and forward it to the client."""
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'inbox_update',
                    'conversation_id': event['conversation_id'],
                    'sender_id': event['sender_id'],
                    'sender_name': event['sender_name'],
                    'content': event['content'],
                    'created_at': event['created_at'],
                }
            )
        )

import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from chat.models import Message
from datetime import datetime
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"

        qs = parse_qs(self.scope["query_string"].decode())
        token = qs.get("token", [None])[0]

        if not token:
            logger.error("No token provided")
            await self.close()
            return

        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
        except Exception as e1:
            import jwt
            try:
                payload = jwt.decode(
                    token,
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithms=['HS256']
                )
                user_id = payload['user_id']
            except Exception as e2:
                logger.error(f"Token decode failed: {e1} | {e2}")
                await self.close()
                return

        try:
            self.user = await self.get_user(user_id)
            self.username = self.user.username
        except Exception as e:
            logger.error(f"User fetch failed: {e}")
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "welcome",
            "message": f"Welcome {self.username}! You are connected.",
            "user": self.username
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '').strip()

        if message:
            await self.save_message(message)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "user": self.username
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event["message"],
            "user": event["user"]
        }))

    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)

    @database_sync_to_async
    def save_message(self, message):
        Message.objects.create(
            value=message,
            user=self.username,
            room=self.room_name,
            date=datetime.now()
        )
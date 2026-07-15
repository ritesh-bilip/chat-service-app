import json
import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Parse token and username variables cleanly out of the query string string layout
        query_string = self.scope.get('query_string', b'').decode()
        token = None
        passed_username = None
        
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=')[1]
            elif param.startswith('username='):
                from urllib.parse import unquote
                passed_username = unquote(param.split('=')[1])

        # Authenticate and synchronize database structure safely
        self.user = await self.get_user_from_token(token, passed_username)

        if self.user:
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
            
            # Send welcome message
            await self.send(text_data=json.dumps({
                'type': 'welcome',
                'message': f'Welcome to {self.room_name}!'
            }))
        else:
            await self.close(code=403)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': self.user.username
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'user': event['user']
        }))

    async def get_user_from_token(self, token, passed_username):
        if not token:
            return None
        try:
            payload = jwt.decode(token, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=["HS256"])
            user_id = payload.get('user_id')
            
            # Fallback if front-end failed extraction loops
            real_name = passed_username if (passed_username and passed_username != "Anonymous") else f'User_{user_id}'
            
            # Automatically builds or syncs profile context in SQLite records
            user = await self.sync_user_to_db(user_id, real_name)
            return user
        except Exception as e:
            print(f"Token validation/sync failed: {e}")
            return None

    @database_sync_to_async
    def sync_user_to_db(self, user_id, real_name):
        user, created = User.objects.get_or_create(
            id=user_id,
            defaults={'username': real_name}
        )
        if not created and user.username != real_name:
            user.username = real_name
            user.save()
        return user
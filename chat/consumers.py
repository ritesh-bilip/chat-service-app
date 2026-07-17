import json
import jwt
from urllib.parse import unquote
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # ── Parse query string safely ──────────────────────────────
        # Old code used param.split('=')[1] which truncates tokens
        # that contain '=' characters. split('=', 1) fixes that.
        raw_qs = self.scope.get('query_string', b'').decode()
        params = {}
        for part in raw_qs.split('&'):
            if '=' in part:
                key, value = part.split('=', 1)   # maxsplit=1 is critical
                params[key] = unquote(value)

        token       = params.get('token')
        passed_name = params.get('username', '').strip()

        # ── Validate JWT and get the real username ─────────────────
        self.username = self.get_username_from_token(token, passed_name)

        if self.username:
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'welcome',
                'message': f'Welcome to {self.room_name}, {self.username}!'
            }))
        else:
            await self.close(code=4003)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data    = json.loads(text_data)
        message = data.get('message', '').strip()
        if not message:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type':    'chat_message',
                'message': message,
                'user':    self.username,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':    'message',
            'message': event['message'],
            'user':    event['user'],
        }))

    # ──────────────────────────────────────────────────────────────
    # FIX: removed sync_user_to_db entirely.
    #
    # OLD: decoded JWT → got user_id → DB write on every connect
    #      if DB write failed → silent 403
    #
    # NEW: decoded JWT → read payload.name directly
    #      (name baked in by CustomRefreshToken in auth service)
    #      no DB access, no failure point, faster connections
    # ──────────────────────────────────────────────────────────────
    def get_username_from_token(self, token, passed_name):
        if not token:
            print("[WS] Rejected: no token")
            return None
        try:
            signing_key = settings.SIMPLE_JWT.get('SIGNING_KEY', settings.SECRET_KEY)
            payload = jwt.decode(token, signing_key, algorithms=["HS256"])

            # Priority 1: name from JWT payload (set by CustomRefreshToken)
            # Priority 2: username from URL param
            # Priority 3: fallback to user_id
            name = (
                payload.get('name')
                or (passed_name if passed_name and passed_name != 'Anonymous' else None)
                or f"User_{payload.get('user_id', 'unknown')}"
            )
            print(f"[WS] Accepted: user='{name}' room='{self.room_name}'")
            return name

        except jwt.ExpiredSignatureError:
            print("[WS] Rejected: token expired")
        except jwt.InvalidSignatureError:
            print("[WS] Rejected: invalid signature — JWT_SECRET mismatch?")
        except jwt.DecodeError as e:
            print(f"[WS] Rejected: decode error — {e}")
        except Exception as e:
            print(f"[WS] Rejected: unexpected — {e}")
        return None
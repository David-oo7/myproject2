import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import ChatMessage

ROOM_GROUP_NAME = 'muhokama_xonasi'

# Ruxsat etilgan stiker emojilar (O'rta Yer mavzusida, original)
ALLOWED_STICKERS = {
    '💍', '⚔️', '🏹', '🪓', '🌳', '🏔️', '🐴', '🔥',
    '✨', '🛡️', '🌙', '⭐', '👑', '🗡️', '🦅', '🌲',
}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(ROOM_GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(ROOM_GROUP_NAME, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        name = (data.get('name') or 'Mehmon').strip()[:60]
        msg_type = data.get('type', 'text')

        if msg_type == 'sticker':
            sticker = (data.get('sticker') or '').strip()
            if sticker not in ALLOWED_STICKERS:
                return
            message = await self.save_message(name, message_type=ChatMessage.STICKER, sticker=sticker)
            payload = {
                'type': 'chat_message',
                'name': message.name,
                'message_type': 'sticker',
                'sticker': message.sticker,
                'created_at': message.created_at.strftime('%H:%M'),
            }
        else:
            text = (data.get('text') or '').strip()[:500]
            if not text:
                return
            message = await self.save_message(name, message_type=ChatMessage.TEXT, text=text)
            payload = {
                'type': 'chat_message',
                'name': message.name,
                'message_type': 'text',
                'text': message.text,
                'created_at': message.created_at.strftime('%H:%M'),
            }

        await self.channel_layer.group_send(ROOM_GROUP_NAME, payload)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'name': event.get('name'),
            'message_type': event.get('message_type', 'text'),
            'text': event.get('text', ''),
            'image_url': event.get('image_url', ''),
            'sticker': event.get('sticker', ''),
            'created_at': event.get('created_at'),
        }))

    @database_sync_to_async
    def save_message(self, name, message_type='text', text='', sticker=''):
        return ChatMessage.objects.create(
            name=name or 'Mehmon',
            message_type=message_type,
            text=text,
            sticker=sticker,
        )

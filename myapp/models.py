from django.db import models


class ChatMessage(models.Model):
    TEXT = 'text'
    IMAGE = 'image'
    STICKER = 'sticker'
    TYPE_CHOICES = [
        (TEXT, 'Matn'),
        (IMAGE, 'Rasm'),
        (STICKER, 'Stiker'),
    ]

    name = models.CharField(max_length=60)
    text = models.TextField(max_length=500, blank=True)
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TEXT)
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)
    sticker = models.CharField(max_length=10, blank=True)  # emoji-stiker belgisi
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name}: {self.text[:30]}"

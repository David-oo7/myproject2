from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import os
import json
import requests

from .models import ChatMessage
from .forms import RegisterForm


def home(request):
    chat_messages = ChatMessage.objects.order_by('-created_at')[:50][::-1]
    return render(request, 'index.html', {'chat_messages': chat_messages})


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            django_messages.success(request, "Ro'yxatdan muvaffaqiyatli o'tdingiz! Xush kelibsiz.")
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


@login_required
@require_POST
def chat_upload_image(request):
    name = request.user.username
    image_file = request.FILES.get('image')

    if not image_file:
        return JsonResponse({'error': "Rasm topilmadi"}, status=400)
    if image_file.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({'error': "Faqat JPG, PNG, GIF yoki WEBP formatidagi rasmlar qabul qilinadi"}, status=400)
    if image_file.size > MAX_IMAGE_SIZE:
        return JsonResponse({'error': "Rasm hajmi 5MB dan oshmasligi kerak"}, status=400)

    message = ChatMessage.objects.create(
        name=name or 'Mehmon',
        message_type=ChatMessage.IMAGE,
        image=image_file,
    )

    payload = {
        'name': message.name,
        'message_type': 'image',
        'image_url': message.image.url,
        'created_at': message.created_at.strftime('%H:%M'),
    }

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'muhokama_xonasi',
        {'type': 'chat_message', **payload}
    )

    return JsonResponse({'id': message.id, **payload})


# ==================== GANDALF AI YORDAMCHISI ====================
# Gemini asosiy, Groq zaxira (limit tugasa yoki xatolik bo'lsa avtomatik o'tadi).
# API kalitlar hech qachon kodga yozilmaydi — Render'ning "Environment Variables"
# bo'limidan GEMINI_API_KEY va GROQ_API_KEY nomlari bilan o'qib olinadi.

TOLKIEN_KEYWORDS=[
    "gandalf",
    "frodo",
    "aragorn",
    "legolas",
    "gimli",
    "sauron",
    "saruman",
    "mordor",
    "shire",
    "hobbit",
    "lotr",
    "uzuk",
    "ring",
    "middle-earth",
    "o'rta yer",
    "orta yer",
    "elf",
    "orc",
    "rohan",
    "gondor",
    "rivendell",
    "valinor",
    "numenor",
]

GANDALF_SYSTEM_PROMPT = (
    "Sen Gandalfsan. Faqat Tolkien yaratgan O'rta Yer olami bo'yicha javob beradigan "
    "yordamchi sehrgarsan. O'zbek tilida javob ber. Javoblaring qisqa, aniq va "
    "foydali bo'lsin, lekin gohida donishmandona metafora yoki hikmat bilan "
    "boyitib qo'y. Faqat foydalanuvchi so'ragan savolga javob ber; hech qanday "
    "haqiqiy kitob yoki film matnini so'zma-so'z keltirma, faqat o'z uslubingda gapir."
)


def _ask_gemini(question, api_key):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key=" + api_key
    )
    body = {
        "contents": [{"parts": [{"text": question}]}],
        "systemInstruction": {"parts": [{"text": GANDALF_SYSTEM_PROMPT}]},
    }
    resp = requests.post(url, json=body, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _ask_groq(question, api_key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": GANDALF_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    }
    resp = requests.post(url, headers=headers, json=body, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


@require_POST
def ask_gandalf(request):
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': "Noto'g'ri so'rov"}, status=400)

    question = (data.get('question') or '').strip()[:1000]
    if not any(k in question.lower() for k in TOLKIEN_KEYWORDS):
        return JsonResponse({'answer':'Men Gandalfman. Men faqat Tolkien yaratgan Oʻrta Yer olami haqida bilimga egaman. Bu savolga javob bera olmayman.'})
    if not question:
        return JsonResponse({'error': "Savolingizni yozing"}, status=400)

    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    groq_key = os.environ.get('GROQ_API_KEY', '')

    # 1) Avval Gemini bilan urinib ko'ramiz
    if gemini_key:
        try:
            answer = _ask_gemini(question, gemini_key)
            return JsonResponse({'answer': answer, 'source': 'gemini'})
        except Exception:
            pass  # Gemini ishlamasa (limit/xato) — Groq'ga o'tamiz

    # 2) Zaxira: Groq
    if groq_key:
        try:
            answer = _ask_groq(question, groq_key)
            return JsonResponse({'answer': answer, 'source': 'groq'})
        except Exception:
            pass

    return JsonResponse(
        {'error': "Gandalf hozircha javob bera olmayapti. Birozdan so'ng qayta urinib ko'ring."},
        status=503,
    )

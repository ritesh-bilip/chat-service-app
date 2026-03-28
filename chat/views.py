from django.shortcuts import render, redirect
from chat.models import Room,Message
from django.http import JsonResponse
# Create your views here.
def home(request):
  token=request.GET.get("token")
  return render(request,'home.html',{"token":token})
def room(request,room):
  token=request.GET.get("token")
  user = request.user if request.user.is_authenticated else None
  return render(request, "room.html", {
        "room": room,
        "token": token,
        "username": user.username if user else "Anonymous"
    })



from django.http import JsonResponse
from .models import Room
from rest_framework_simplejwt.tokens import AccessToken

def checkview(request):
    room = request.POST.get('room_name')  # ✅ FIXED: was missing
    username = request.POST.get('username', 'Anonymous')

    # Get token from session/localStorage or issue new one
    token = request.POST.get('token')
    if not token and request.user.is_authenticated:
        token = str(AccessToken.for_user(request.user))

    if Room.objects.filter(name=room).exists():
        return JsonResponse({"redirect": f"/{room}/?token={token}"})
    else:
        new_room = Room.objects.create(name=room)
        return JsonResponse({"redirect": f"/{room}/?token={token}"})

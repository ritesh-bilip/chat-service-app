from django.shortcuts import render
from chat.models import Room, Message
from django.http import JsonResponse
from rest_framework_simplejwt.tokens import AccessToken

def home(request):
    token = request.GET.get("token")
    return render(request, 'home.html', {"token": token})

def room(request, room):
    token = request.GET.get("token")
    
    # ✅ FIXED: Now properly checks for 'username' since we confirmed the standard User model is used
    display_name = request.user.username if request.user.is_authenticated else "Anonymous"
    
    return render(request, "room.html", {
        "room": room,
        "token": token,
        "username": display_name
    })

def checkview(request):
    room = request.POST.get('room_name')
    token = request.POST.get('token')
    
    if not token and request.user.is_authenticated:
        token = str(AccessToken.for_user(request.user))

    if Room.objects.filter(name=room).exists():
        return JsonResponse({"redirect": f"{room}/?token={token}"})
    else:
        Room.objects.create(name=room)
        return JsonResponse({"redirect": f"{room}/?token={token}"})
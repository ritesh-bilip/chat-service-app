from django.urls import path, re_path
from chat import views, consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>\w+)/$', consumers.ChatConsumer.as_asgi()),
]

urlpatterns = [
    path('', views.home, name='home'),
    path('checkview', views.checkview, name='checkview'),
    re_path(r'^(?P<room>[^/]+)/$', views.room, name='room'),
]

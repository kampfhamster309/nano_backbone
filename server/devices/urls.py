from django.urls import path
from . import views

urlpatterns = [
    path("devices/register/", views.register_device, name="device-register"),
    path("ping/", views.ping, name="ping"),
]

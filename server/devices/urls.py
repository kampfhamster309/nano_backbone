from django.urls import path
from . import views

urlpatterns = [
    path("devices/register/", views.register_device, name="device-register"),
    path("devices/events/", views.report_event, name="device-event"),
    path("ping/", views.ping, name="ping"),
]

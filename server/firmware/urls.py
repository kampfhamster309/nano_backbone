from django.urls import path
from . import views

urlpatterns = [
    path("firmware/latest/", views.latest_firmware, name="firmware-latest"),
]

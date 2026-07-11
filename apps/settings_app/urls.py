from django.urls import path
from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.settings_home, name="home"),
    path("whatsapp/", views.whatsapp_settings, name="whatsapp"),
    path("whatsapp/webhook/", views.whatsapp_webhook, name="whatsapp_webhook"),
]

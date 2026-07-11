from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("", views.payments_list, name="list"),
    path("order/<str:order_no>/", views.payment_detail, name="detail"),
]

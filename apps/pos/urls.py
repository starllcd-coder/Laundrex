from django.urls import path
from . import views

app_name = "pos"

urlpatterns = [
    path("", views.new_order, name="new_order"),
    path("receipt/80mm/", views.receipt_80mm, name="receipt_80mm"),
    path("api/create-order/", views.create_order_api, name="create_order_api"),
]

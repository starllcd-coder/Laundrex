from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog_home, name="home"),
    path("seed/", views.seed_defaults, name="seed"),
    path("api/pos-data/", views.pos_data_api, name="pos_data_api"),
]

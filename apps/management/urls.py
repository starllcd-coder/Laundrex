from django.urls import path
from . import views

app_name = "management"

urlpatterns = [
    path("", views.management_home, name="home"),
    path("branches/", views.branch_list, name="branches"),
    path("branches/<int:branch_id>/", views.branch_detail, name="branch_detail"),
    path("staff/", views.staff_list, name="staff"),
    path("staff/add/", views.staff_create, name="staff_add"),
    path("staff/<int:user_id>/", views.staff_detail, name="staff_detail"),
    path("audit/", views.audit_logs, name="audit_logs"),
]

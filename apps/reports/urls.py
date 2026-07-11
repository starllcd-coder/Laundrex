from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_home, name="home"),
    path("z-report/", views.z_report, name="z_report"),
    path("z-report/export/pdf/", views.export_z_report_pdf, name="export_z_pdf"),
    path("export/csv/", views.export_reports_csv, name="export_csv"),
    path("export/excel/", views.export_reports_excel, name="export_excel"),
    path("export/pdf/", views.export_reports_pdf, name="export_pdf"),
]

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.orders import views as order_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", lambda request: redirect("accounts:login"), name="login_redirect"),
    path("p/<str:token>/", order_views.pickup_public, name="pickup_public"),
    path("api/", include(("apps.mobile_api.urls", "mobile_api"), namespace="mobile_api")),
    path("", include(("apps.core.urls", "core"), namespace="core")),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("management/", include(("apps.management.urls", "management"), namespace="management")),
    path("pos/", include(("apps.pos.urls", "pos"), namespace="pos")),
    path("orders/", include(("apps.orders.urls", "orders"), namespace="orders")),
    path("payments/", include(("apps.payments.urls", "payments"), namespace="payments")),
    path("reports/", include(("apps.reports.urls", "reports"), namespace="reports")),
    path("settings/", include(("apps.settings_app.urls", "settings_app"), namespace="settings_app")),
    path("catalog/", include(("apps.catalog.urls", "catalog"), namespace="catalog")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

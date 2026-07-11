from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AddressDetailView, AddressListCreateView, BankTransferProofView, DeviceTokenView, LaundryCatalogView, LaundryDetailView,
    LaundryListView, AnalyticsEventView, AppConfigView, ForgotPasswordView, LoginView, LogoutView, OtpSendView,
    NotificationListView, NotificationReadView, OtpVerifyView, OrderCancelView, OrderDetailView, OrderListCreateView, OrderPricePreviewView, OrderTrackingView,
    ProfileView,
    RegisterView, ResetPasswordView, SocialLoginView, payment_methods_view,
)

urlpatterns = [
    path("app-config", AppConfigView.as_view()),
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("auth/profile", ProfileView.as_view()),
    path("auth/otp/send", OtpSendView.as_view()),
    path("auth/otp/verify", OtpVerifyView.as_view()),
    path("auth/forgot-password", ForgotPasswordView.as_view()),
    path("auth/reset-password", ResetPasswordView.as_view()),
    path("auth/google", SocialLoginView.as_view(provider="google")),
    path("auth/apple", SocialLoginView.as_view(provider="apple")),
    path("auth/social", SocialLoginView.as_view()),
    path("auth/token/refresh", TokenRefreshView.as_view()),

    path("laundries", LaundryListView.as_view()),
    path("laundries/<int:pk>", LaundryDetailView.as_view()),
    path("laundries/<int:pk>/catalog", LaundryCatalogView.as_view()),

    path("addresses", AddressListCreateView.as_view()),
    path("addresses/<int:pk>", AddressDetailView.as_view()),

    path("orders", OrderListCreateView.as_view()),
    path("orders/<int:pk>", OrderDetailView.as_view()),
    path("orders/<int:pk>/cancel", OrderCancelView.as_view()),
    path("orders/<int:pk>/tracking", OrderTrackingView.as_view()),
    path("orders/<int:pk>/bank-transfer-proof", BankTransferProofView.as_view()),
    path("orders/price-preview", OrderPricePreviewView.as_view()),

    path("devices", DeviceTokenView.as_view()),
    path("analytics", AnalyticsEventView.as_view()),
    path("notifications", NotificationListView.as_view()),
    path("notifications/read", NotificationReadView.as_view()),

    path("payment-methods", payment_methods_view),
]

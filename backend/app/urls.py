"""App URL configuration."""

from django.urls import path
from .views import PayoutCreateView, DashboardView, MerchantListView

urlpatterns = [
    path("payouts", PayoutCreateView.as_view(), name="payout-create"),
    path("dashboard", DashboardView.as_view(), name="dashboard"),
    path("merchants", MerchantListView.as_view(), name="merchant-list"),
]

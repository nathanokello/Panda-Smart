from django.urls import path

from planting.views import (
    AdviceView,
    DashboardWardDetailView,
    DashboardWardsView,
    PlantingIntentListCreateView,
    UssdView,
    WardSlotsView,
)

urlpatterns = [
    path("advice/", AdviceView.as_view(), name="advice"),
    path("planting-intents/", PlantingIntentListCreateView.as_view(), name="planting-intent-list"),
    path("wards/<uuid:ward_id>/slots/", WardSlotsView.as_view(), name="ward-slots"),
    path("dashboard/wards/", DashboardWardsView.as_view(), name="dashboard-wards"),
    path("dashboard/wards/<uuid:ward_id>/", DashboardWardDetailView.as_view(), name="dashboard-ward"),
    path("ussd/", UssdView.as_view(), name="ussd"),
]

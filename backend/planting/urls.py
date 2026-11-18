from django.urls import path

from planting.views import (
    AdviceView,
    DashboardWardDetailView,
    DashboardWardsView,
    FarmerHistoryView,
    FarmerSeasonsView,
    FarmerSoilTestsView,
    MyDashboardView,
    SeasonRecordDetailView,
    PlantingIntentListCreateView,
    ProduceListingListCreateView,
    ProduceListingStatusView,
    UssdView,
    WardSlotsView,
    WardWeatherView,
)

urlpatterns = [
    path("marketplace/", ProduceListingListCreateView.as_view(), name="produce-listing-list"),
    path("marketplace/<uuid:listing_id>/", ProduceListingStatusView.as_view(), name="produce-listing-status"),
    path("advice/", AdviceView.as_view(), name="advice"),
    path("farmers/<uuid:farmer_id>/seasons/", FarmerSeasonsView.as_view(), name="farmer-seasons"),
    path("farmers/<uuid:farmer_id>/soil-tests/", FarmerSoilTestsView.as_view(), name="farmer-soil-tests"),
    path("farmers/<uuid:farmer_id>/history/", FarmerHistoryView.as_view(), name="farmer-history"),
    path("seasons/<uuid:pk>/", SeasonRecordDetailView.as_view(), name="season-detail"),
    path("planting-intents/", PlantingIntentListCreateView.as_view(), name="planting-intent-list"),
    path("wards/<uuid:ward_id>/slots/", WardSlotsView.as_view(), name="ward-slots"),
    path("wards/<uuid:ward_id>/weather/", WardWeatherView.as_view(), name="ward-weather"),
    path("dashboard/me/", MyDashboardView.as_view(), name="dashboard-me"),
    path("dashboard/wards/", DashboardWardsView.as_view(), name="dashboard-wards"),
    path("dashboard/wards/<uuid:ward_id>/", DashboardWardDetailView.as_view(), name="dashboard-ward"),
    path("ussd/", UssdView.as_view(), name="ussd"),
]

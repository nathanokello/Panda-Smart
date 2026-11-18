from django.urls import path
from .views import FarmListCreateView, FarmDetailView, FarmEnvironmentView, CropSuitabilityView, RegionalSupplyView, PlantingIntentView
urlpatterns = [
    path("geoagri/farms/", FarmListCreateView.as_view(), name="geoagri-farms"),
    path("geoagri/farms/<uuid:pk>/", FarmDetailView.as_view(), name="geoagri-farm-detail"),
    path("geoagri/farms/<uuid:pk>/environment/", FarmEnvironmentView.as_view(), name="geoagri-farm-environment"),
    path("geoagri/farms/<uuid:pk>/suitability/", CropSuitabilityView.as_view(), name="geoagri-suitability"),
    path("geoagri/regional-supply/", RegionalSupplyView.as_view(), name="geoagri-regional-supply"),
    path("geoagri/planting-intents/", PlantingIntentView.as_view(), name="geoagri-planting-intents"),
]

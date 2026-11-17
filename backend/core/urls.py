from django.urls import path

from core.views import (
    CropListView,
    FarmerDetailView,
    FarmerListCreateView,
    LoginView,
    MeView,
    PlotListCreateView,
    WardListView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("wards/", WardListView.as_view(), name="ward-list"),
    path("crops/", CropListView.as_view(), name="crop-list"),
    path("farmers/", FarmerListCreateView.as_view(), name="farmer-list"),
    path("farmers/<uuid:pk>/", FarmerDetailView.as_view(), name="farmer-detail"),
    path("farmers/<uuid:pk>/plots/", PlotListCreateView.as_view(), name="farmer-plots"),
]

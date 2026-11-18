from django.urls import path

from core.views import (
    CropListView,
    FarmerDetailView,
    FarmerListCreateView,
    FarmerSelfRegisterView,
    LoginView,
    LogoutView,
    MeView,
    PlotListCreateView,
    StaffUserDetailView,
    StaffUserListCreateView,
    TenantListView,
    WardListView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/register/farmer/", FarmerSelfRegisterView.as_view(), name="auth-register-farmer"),
    path("wards/", WardListView.as_view(), name="ward-list"),
    path("crops/", CropListView.as_view(), name="crop-list"),
    path("farmers/", FarmerListCreateView.as_view(), name="farmer-list"),
    path("farmers/<uuid:pk>/", FarmerDetailView.as_view(), name="farmer-detail"),
    path("farmers/<uuid:pk>/plots/", PlotListCreateView.as_view(), name="farmer-plots"),
    path("tenants/", TenantListView.as_view(), name="tenant-list"),
    path("users/", StaffUserListCreateView.as_view(), name="staff-user-list"),
    path("users/<uuid:pk>/", StaffUserDetailView.as_view(), name="staff-user-detail"),
]

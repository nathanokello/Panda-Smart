from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import HealthSlashView, HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", HealthView.as_view(), name="health-no-slash"),
    path("health/", HealthSlashView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("records.urls")),
    path("api/v1/", include("planting.urls")),
]

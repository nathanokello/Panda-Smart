from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from core.models import Plot, User
from .models import FarmProfile, EnvironmentalObservation, CropRequirement, SuitabilityAssessment, RegionalPlantingIntent
from .serializers import FarmSerializer, EnvironmentalObservationSerializer, RegionalIntentSerializer


def farmer_plots(user):
    if user.role in (User.Roles.ADMIN, User.Roles.COOP_ADMIN, User.Roles.AGENT):
        qs = Plot.objects.select_related("farmer", "ward")
        if user.role != User.Roles.ADMIN and user.tenant_id:
            qs = qs.filter(farmer__tenant_id=user.tenant_id)
        return qs
    farmer = getattr(user, "farmer_profile", None)
    return Plot.objects.filter(farmer=farmer) if farmer else Plot.objects.none()

class FarmListCreateView(generics.ListCreateAPIView):
    throttle_scope = "geoagri_write"
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return FarmProfile.objects.filter(plot__in=farmer_plots(self.request.user)).select_related("plot", "plot__ward", "plot__farmer")

class FarmDetailView(generics.RetrieveUpdateDestroyAPIView):
    throttle_scope = "geoagri_write"
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return FarmProfile.objects.filter(plot__in=farmer_plots(self.request.user))

class FarmEnvironmentView(APIView):
    throttle_scope = "geoagri_read"
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, pk):
        plot = farmer_plots(request.user).filter(pk=pk).first()
        if not plot: return Response({"detail": "Farm not found."}, status=404)
        if not hasattr(plot, "geoagri_profile") or not plot.geoagri_profile.location_consent:
            return Response({"detail": "Location consent is required before retrieving farm-specific environmental information."}, status=403)
        qs = EnvironmentalObservation.objects.filter(plot=plot)
        return Response({"farm_id": str(plot.id), "observations": EnvironmentalObservationSerializer(qs[:100], many=True).data, "message": "No observations are available yet. No environmental values have been fabricated."})

class CropSuitabilityView(APIView):
    throttle_scope = "geoagri_read"
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, pk):
        plot = farmer_plots(request.user).filter(pk=pk).first()
        if not plot: return Response({"detail": "Farm not found."}, status=404)
        observations = EnvironmentalObservation.objects.filter(plot=plot)
        results = []
        for crop in CropRequirement.objects.filter(verified=True).values_list("crop_code", "crop_name").distinct():
            code, name = crop
            requirements = CropRequirement.objects.filter(crop_code=code, verified=True)
            matched, missing, constraints = 0, [], []
            for req in requirements:
                obs = observations.filter(variable=req.variable).order_by("-observed_at").first()
                if not obs or obs.value is None:
                    missing.append(req.variable); continue
                matched += 1
                if req.minimum is not None and obs.value < req.minimum: constraints.append(f"{req.variable} below documented minimum")
                if req.maximum is not None and obs.value > req.maximum: constraints.append(f"{req.variable} above documented maximum")
            if not requirements.exists() or not matched:
                classification, score = "insufficient_data", None
            elif constraints:
                classification, score = "unsuitable", 0
            elif missing:
                classification, score = "insufficient_data", None
            else:
                classification, score = "suitable", 100
            results.append({"crop_code": code, "crop_name": name, "classification": classification, "score": score, "constraints": constraints, "missing_information": missing, "requirements_count": requirements.count(), "matched_count": matched})
        return Response({"farm_id": str(plot.id), "assessed_at": timezone.now(), "results": results, "note": "Only verified, source-backed crop requirements are evaluated. This is environmental suitability, not a yield or profit guarantee."})

class RegionalSupplyView(APIView):
    throttle_scope = "geoagri_read"
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        # Only voluntarily shared intentions are aggregated; individual farm data is never returned.
        rows = RegionalPlantingIntent.objects.filter(share_for_aggregation=True).values("plot__ward__county", "plot__ward__name", "crop_code").annotate(farms=Count("plot", distinct=True), planned_kg=Sum("expected_quantity_kg"))
        return Response({"aggregation": list(rows), "privacy": "Only opt-in intentions are included. No individual farmer names, coordinates or plot identifiers are exposed."})

class PlantingIntentView(generics.ListCreateAPIView):
    throttle_scope = "geoagri_write"
    serializer_class = RegionalIntentSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self): return RegionalPlantingIntent.objects.filter(plot__in=farmer_plots(self.request.user))
    def perform_create(self, serializer):
        plot_id = self.request.data.get("plot")
        plot = farmer_plots(self.request.user).filter(pk=plot_id).first()
        if not plot: raise ValidationError("Select one of your own farms.")
        serializer.save(plot=plot)

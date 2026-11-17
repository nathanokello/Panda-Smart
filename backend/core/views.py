from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.models import Crop, Farmer, Plot, Ward
from core.permissions import RolePermission
from core.serializers import (
    CropSerializer,
    FarmerCreateSerializer,
    FarmerSerializer,
    HealthResponseSerializer,
    LoginSerializer,
    PlotCreateSerializer,
    PlotSerializer,
    TokenResponseSerializer,
    UserSerializer,
    WardSerializer,
)

STAFF_ROLES = ("agent", "coop_admin", "admin")
ALL_ROLES = ("farmer", "agent", "coop_admin", "admin")


class HealthView(APIView):
    """Public liveness check for uptime monitors."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=HealthResponseSerializer)
    def get(self, request):
        return Response({"status": "ok"})


@extend_schema(exclude=True)
class HealthSlashView(HealthView):
    """Same health check with a trailing slash; excluded from the schema."""


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=TokenResponseSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class WardListView(generics.ListAPIView):
    queryset = Ward.objects.all()
    serializer_class = WardSerializer


class CropListView(generics.ListAPIView):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer


class FarmerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = STAFF_ROLES

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FarmerCreateSerializer
        return FarmerSerializer

    def get_queryset(self):
        return services.farmers_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        farmer = services.register_farmer(request.user, serializer.validated_data)
        output = FarmerSerializer(farmer, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class FarmerDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = ALL_ROLES
    serializer_class = FarmerSerializer

    def get_queryset(self):
        return services.farmers_for_user(self.request.user)

    def get_object(self):
        farmer = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        if not services.farmer_is_visible(farmer, self.request.user):
            raise PermissionDenied("You may only view your own farmer record.")
        return farmer


class PlotListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = ALL_ROLES

    def get_farmer(self):
        farmer = get_object_or_404(Farmer, pk=self.kwargs["pk"])
        if not services.farmer_is_visible(farmer, self.request.user):
            raise PermissionDenied("You may only view your own plots.")
        return farmer

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PlotCreateSerializer
        return PlotSerializer

    def get_queryset(self):
        return Plot.objects.filter(farmer=self.get_farmer()).select_related("farmer", "ward")

    def perform_create(self, serializer):
        serializer.save(farmer=self.get_farmer())

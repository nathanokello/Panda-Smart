from django.contrib.auth.models import update_last_login
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core import services
from core.authentication import LoginPhoneThrottle, issue_token
from core.models import Crop, Farmer, Plot, User, Ward
from core.permissions import RolePermission
from core.serializers import (
    CropSerializer,
    FarmerCreateSerializer,
    FarmerSelfRegisterSerializer,
    FarmerSerializer,
    HealthResponseSerializer,
    LoginSerializer,
    PlotCreateSerializer,
    PlotSerializer,
    StaffUserCreateSerializer,
    StaffUserSerializer,
    StaffUserUpdateSerializer,
    TenantSerializer,
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
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"
    throttle_classes = [ScopedRateThrottle, LoginPhoneThrottle]

    @extend_schema(request=LoginSerializer, responses=TokenResponseSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        update_last_login(None, user)
        token = issue_token(user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class FarmerSelfRegisterView(APIView):
    """Public farmer registration used by register.html. Always creates a farmer."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @extend_schema(request=FarmerSelfRegisterSerializer, responses={201: TokenResponseSerializer})
    def post(self, request):
        serializer = FarmerSelfRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, _farmer = services.self_register_farmer(serializer.validated_data)
        token = issue_token(user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """Delete the caller's token, so a copied or stolen token stops working."""

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class WardListView(generics.ListAPIView):
    # Reference data: public so the sign-up form can list wards. No
    # authentication, so a stale token in the browser cannot cause a 401 here.
    authentication_classes = []
    permission_classes = [AllowAny]
    queryset = Ward.objects.all()
    serializer_class = WardSerializer


class CropListView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
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


USER_ADMIN_ROLES = ("coop_admin", "admin")


class TenantListView(generics.ListAPIView):
    """Cooperatives the caller may assign users to (users.html)."""

    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = USER_ADMIN_ROLES
    serializer_class = TenantSerializer

    def get_queryset(self):
        return services.tenants_for(self.request.user)


class StaffUserListCreateView(generics.ListCreateAPIView):
    """Staff accounts. Admins: all. Coop admins: their cooperative, create agents only."""

    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = USER_ADMIN_ROLES

    def get_serializer_class(self):
        return StaffUserCreateSerializer if self.request.method == "POST" else StaffUserSerializer

    def get_queryset(self):
        return services.staff_users_for(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = StaffUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_staff_user(request.user, serializer.validated_data)
        return Response(
            StaffUserSerializer(user, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class StaffUserDetailView(generics.RetrieveAPIView):
    """GET or PATCH one staff account. There is no DELETE: deactivate instead,
    because lot history points at the agent who recorded it."""

    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = USER_ADMIN_ROLES
    serializer_class = StaffUserSerializer

    def get_queryset(self):
        return services.staff_users_for(self.request.user)

    @extend_schema(request=StaffUserUpdateSerializer, responses=StaffUserSerializer)
    def patch(self, request, *args, **kwargs):
        target = self.get_object()
        serializer = StaffUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_staff_user(request.user, target, serializer.validated_data)
        return Response(StaffUserSerializer(user, context=self.get_serializer_context()).data)

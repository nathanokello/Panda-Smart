from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.renderers import PlainTextRenderer
from core import services as core_services
from core.permissions import RolePermission
from planting import services
from planting.serializers import (
    AdviceQuerySerializer,
    AdviceResponseSerializer,
    DashboardWardSummarySerializer,
    IntentCreateSerializer,
    IntentSerializer,
    SlotQuerySerializer,
    SlotSerializer,
    UssdRequestSerializer,
    WardDashboardSerializer,
)
from planting.ussd import handle_ussd
from records import services as records_services

DASHBOARD_ROLES = ("coop_admin", "admin")
INTENT_READ_ROLES = ("agent", "coop_admin", "admin")
INTENT_WRITE_ROLES = ("farmer", "agent", "admin")


class AdviceView(APIView):
    @extend_schema(parameters=[AdviceQuerySerializer], responses=AdviceResponseSerializer)
    def get(self, request):
        query = AdviceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(
            services.get_advice(query.validated_data["ward"], query.validated_data["crop"])
        )


class PlantingIntentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, RolePermission]

    def get_queryset(self):
        qs = services.intents_for_user(self.request.user)
        params = self.request.query_params
        if params.get("ward"):
            qs = qs.filter(farmer__ward_id=params["ward"])
        if params.get("crop"):
            qs = qs.filter(crop__code=params["crop"])
        if params.get("season"):
            qs = qs.filter(season=params["season"])
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return IntentCreateSerializer
        return IntentSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            self.permission_classes = [IsAuthenticated, RolePermission]
            self.allowed_roles = INTENT_WRITE_ROLES
        else:
            self.permission_classes = [IsAuthenticated, RolePermission]
            self.allowed_roles = INTENT_READ_ROLES
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        # API uses *_id field names; services take model instances.
        data["farmer"] = data.pop("farmer_id")
        data["plot"] = data.pop("plot_id", None)
        intent = services.register_intent(request.user, data)
        return Response(
            IntentSerializer(intent, context=self.get_serializer_context()).data,
            status=201,
        )


class WardSlotsView(APIView):
    @extend_schema(parameters=[SlotQuerySerializer], responses=SlotSerializer(many=True))
    def get(self, request, ward_id):
        ward = core_services.get_ward_or_404(ward_id)
        crop_code = request.query_params.get("crop")
        if not crop_code:
            raise ValidationError({"crop": ["This query parameter is required."]})
        crop = core_services.get_crop_or_404(crop_code)
        season = request.query_params.get("season", services.DEFAULT_SEASON)
        return Response(services.get_slots(ward, crop, season))


class DashboardWardsView(APIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = DASHBOARD_ROLES

    @extend_schema(
        operation_id="dashboard_wards_list", responses=DashboardWardSummarySerializer(many=True)
    )
    def get(self, request):
        return Response(services.get_dashboard_wards())


class DashboardWardDetailView(APIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = DASHBOARD_ROLES

    @extend_schema(operation_id="dashboard_ward_detail", responses=WardDashboardSerializer)
    def get(self, request, ward_id):
        return Response(services.get_ward_dashboard(ward_id))


class UssdView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "ussd"
    parser_classes = [FormParser, MultiPartParser]
    renderer_classes = [PlainTextRenderer]

    @extend_schema(
        request=UssdRequestSerializer,
        responses=OpenApiResponse(description="Plain text starting with CON or END."),
    )
    def post(self, request):
        session_id = request.data.get("sessionId", "")
        phone = request.data.get("phoneNumber", "")
        text = request.data.get("text", "")
        if not session_id or not phone:
            return Response("END Missing sessionId or phoneNumber.")
        return Response(handle_ussd(session_id, phone, text))

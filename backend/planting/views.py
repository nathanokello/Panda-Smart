import hmac

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from django.core.cache import cache
from rest_framework.exceptions import APIException, NotFound, ValidationError
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
    ProduceListingCreateSerializer,
    ProduceListingSerializer,
    ProduceListingStatusSerializer,
    SeasonRecordSerializer,
    SeasonRecordWriteSerializer,
    SoilTestSerializer,
    SlotQuerySerializer,
    SlotSerializer,
    UssdRequestSerializer,
    WardDashboardSerializer,
)
from planting import history, weather
from planting.models import ProduceListing, SeasonRecord, SoilTest
from planting.ussd import handle_ussd
from records.models import Lot


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"
from records import services as records_services

DASHBOARD_ROLES = ("coop_admin", "admin")
# Farmers may list intents too; intents_for_user limits them to their own.
INTENT_READ_ROLES = ("farmer", "agent", "coop_admin", "admin")
INTENT_WRITE_ROLES = ("farmer", "agent", "admin")


class ProduceListingListCreateView(APIView):
    """Public browsing; only signed-in farmers create or manage listings."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), RolePermission()]

    def get(self, request):
        qs = ProduceListing.objects.filter(status=ProduceListing.Statuses.AVAILABLE).select_related(
            "farmer", "crop", "ward", "lot"
        )
        crop = request.query_params.get("crop")
        ward = request.query_params.get("ward")
        if crop:
            qs = qs.filter(crop__code=crop)
        if ward:
            qs = qs.filter(ward_id=ward)
        return Response(ProduceListingSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != "farmer":
            raise ValidationError({"detail": ["Only farmers may create produce listings."]})
        profile = getattr(request.user, "farmer_profile", None)
        if profile is None:
            raise ValidationError({"farmer": ["Your account has no linked farmer profile."]})
        serializer = ProduceListingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        crop = data.pop("crop")
        lot_id = data.pop("lot_id", None)
        lot = None
        if lot_id:
            lot = Lot.objects.filter(pk=lot_id, farmer=profile).first()
            if not lot:
                raise NotFound("Lot not found for your farmer profile.")
        listing = ProduceListing.objects.create(
            farmer=profile,
            crop=crop,
            ward=profile.ward,
            lot=lot,
            **data,
        )
        return Response(ProduceListingSerializer(listing).data, status=201)


class ProduceListingStatusView(APIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = ("farmer",)

    def patch(self, request, listing_id):
        profile = getattr(request.user, "farmer_profile", None)
        listing = ProduceListing.objects.filter(pk=listing_id, farmer=profile).first()
        if not listing:
            raise NotFound("Produce listing not found.")
        serializer = ProduceListingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing.status = serializer.validated_data["status"]
        listing.save(update_fields=["status", "updated_at"])
        return Response(ProduceListingSerializer(listing).data)


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


class WardWeatherView(APIView):
    """7-day forecast for a ward from Open-Meteo, cached for an hour.

    Off unless OPEN_METEO_ENABLED=1, because Open-Meteo's free API is for
    non-commercial use only. Returns {"enabled": false} when off.
    """

    def get(self, request, ward_id):
        ward = core_services.get_ward_or_404(ward_id)
        try:
            return Response(services.get_ward_weather(ward))
        except weather.WeatherSourceError as exc:
            raise ServiceUnavailable("The weather service could not be reached. Try again later.") from exc


class MyDashboardView(APIView):
    """Home-screen summary for a signed-in farmer: farms, land, active crops,
    stored produce, the AI planting recommendation, weather and recent activity.
    """

    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = ("farmer",)

    def get(self, request):
        return Response(services.get_farmer_dashboard(request.user))


class FarmerScopedMixin:
    """Load the farmer in the URL; farmers see only themselves, staff their cooperative."""

    def get_farmer(self):
        farmer = core_services.farmers_for_user(self.request.user).filter(
            pk=self.kwargs["farmer_id"]).first()
        if not farmer or not core_services.farmer_is_visible(farmer, self.request.user):
            raise NotFound("Farmer not found.")
        return farmer


class FarmerSeasonsView(FarmerScopedMixin, generics.ListCreateAPIView):
    """Past and current seasons for one farmer: what was planted and what came of it."""

    serializer_class = SeasonRecordSerializer

    def get_queryset(self):
        return SeasonRecord.objects.filter(farmer=self.get_farmer()).select_related(
            "crop", "plot", "recorded_by")

    @extend_schema(request=SeasonRecordWriteSerializer, responses={201: SeasonRecordSerializer})
    def post(self, request, *args, **kwargs):
        farmer = self.get_farmer()
        serializer = SeasonRecordWriteSerializer(data=request.data, context={"farmer": farmer})
        serializer.is_valid(raise_exception=True)
        record = SeasonRecord.objects.create(farmer=farmer, recorded_by=request.user,
                                             **serializer.validated_data)
        return Response(SeasonRecordSerializer(record).data, status=201)


class SeasonRecordDetailView(APIView):
    """Add the harvest to a season later, or fix a typo. Season records are the
    farmer's planning notes, not proof records, so they can be edited."""

    def get_record(self, request, pk):
        record = SeasonRecord.objects.select_related("farmer", "crop").filter(pk=pk).first()
        if not record or not core_services.farmer_is_visible(record.farmer, request.user):
            raise NotFound("Season record not found.")
        return record

    @extend_schema(responses=SeasonRecordSerializer)
    def get(self, request, pk):
        return Response(SeasonRecordSerializer(self.get_record(request, pk)).data)

    @extend_schema(request=SeasonRecordWriteSerializer, responses=SeasonRecordSerializer)
    def patch(self, request, pk):
        record = self.get_record(request, pk)
        serializer = SeasonRecordWriteSerializer(
            record, data=request.data, partial=True, context={"farmer": record.farmer})
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(record, field, value)
        record.save()
        return Response(SeasonRecordSerializer(record).data)


class FarmerSoilTestsView(FarmerScopedMixin, generics.ListCreateAPIView):
    serializer_class = SoilTestSerializer

    def get_queryset(self):
        return SoilTest.objects.filter(farmer=self.get_farmer()).select_related("plot", "recorded_by")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["farmer"] = self.get_farmer()
        return context

    def perform_create(self, serializer):
        serializer.save(farmer=self.get_farmer(), recorded_by=self.request.user)


class FarmerHistoryView(FarmerScopedMixin, APIView):
    """What worked before: yield per crop across seasons, storage loss, latest soil test."""

    def get(self, request, farmer_id):
        return Response(history.farmer_history(self.get_farmer()))


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
        # The endpoint is public, and menu 3 returns a farmer's private verify
        # link for the phone number in the request. Without a check, anyone
        # could POST a farmer's number and act on their lot. Put the secret in
        # the callback URL you register with Africa's Talking:
        #   https://<host>/api/v1/ussd/?key=<USSD_CALLBACK_SECRET>
        secret = getattr(settings, "USSD_CALLBACK_SECRET", "")
        if secret:
            if not hmac.compare_digest(request.query_params.get("key", ""), secret):
                return Response("END Not authorised.", status=403)
        elif not settings.DEBUG:
            return Response("END Service not configured.", status=503)
        session_id = request.data.get("sessionId", "")
        phone = request.data.get("phoneNumber", "")
        text = request.data.get("text", "")
        if not session_id or not phone:
            return Response("END Missing sessionId or phoneNumber.")
        return Response(handle_ussd(session_id, phone, text))

import uuid

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User
from core.permissions import RolePermission
from records import services
from records.models import Lot, LotEvent
from records.serializers import (
    EventCreateSerializer,
    LotEventSerializer,
    LotRegisterSerializer,
    LotSerializer,
    DisputeRequestSerializer,
    VerifyActionResponseSerializer,
    VerifyChainResponseSerializer,
    VerifyDataSerializer,
)

STAFF_ROLES = ("agent", "coop_admin", "admin")
WRITE_ROLES = ("agent", "admin")


class MyVerificationLinksView(APIView):
    """A farmer's own pending produce-record verification links.

    Reuses the same lookup as the USSD 'verify my grain' menu, so a farmer
    sees the same links here as they would get by SMS/USSD.
    """

    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = ("farmer",)

    def get(self, request):
        profile = getattr(request.user, "farmer_profile", None)
        if profile is None:
            return Response({"links": []})
        return Response({"links": services.get_verification_links_for_farmer(profile.id)})


def _uuid_filter(qs, field, value):
    try:
        uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({field: ["Must be a valid UUID."]}) from exc
    return qs.filter(**{field: value})


class LotListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = STAFF_ROLES + ("farmer",)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LotRegisterSerializer
        return LotSerializer

    def get_queryset(self):
        qs = services.lots_for_user(self.request.user)
        params = self.request.query_params
        if params.get("ward"):
            qs = _uuid_filter(qs, "ward_id", params["ward"])
        if params.get("farmer"):
            qs = _uuid_filter(qs, "farmer_id", params["farmer"])
        if params.get("crop"):
            qs = qs.filter(crop__code=params["crop"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        if request.user.role not in WRITE_ROLES and not request.user.is_superuser:
            raise PermissionDenied("Only storage agents may register lots.")
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        # API uses farmer_id; the service takes a Farmer instance.
        data["farmer"] = data.pop("farmer_id")
        lot, _token = services.register_lot(request.user, data)
        return Response(
            LotSerializer(lot, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class LotDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = STAFF_ROLES + ("farmer",)
    serializer_class = LotSerializer

    def get_queryset(self):
        return services.lots_for_user(self.request.user)


class LotEventsView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = STAFF_ROLES + ("farmer",)

    def get_lot(self):
        return services.get_lot_for_user(self.kwargs["lot_id"], self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return EventCreateSerializer
        return LotEventSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == "POST":
            context["lot"] = self.get_lot()
        return context

    def get_queryset(self):
        return LotEvent.objects.filter(lot=self.get_lot()).select_related("recorded_by")

    def create(self, request, *args, **kwargs):
        if request.user.role not in WRITE_ROLES and not request.user.is_superuser:
            raise PermissionDenied("Only storage agents may add lot events.")
        lot = self.get_lot()
        serializer = self.get_serializer(data=request.data, context={"lot": lot, "request": request})
        serializer.is_valid(raise_exception=True)
        event = services.add_event(
            request.user, lot, serializer.validated_data["type"], serializer.validated_data["payload"]
        )
        return Response(
            LotEventSerializer(event).data, status=status.HTTP_201_CREATED
        )


class VerifyChainView(APIView):
    permission_classes = [IsAuthenticated, RolePermission]
    allowed_roles = STAFF_ROLES + ("farmer",)

    @extend_schema(responses=VerifyChainResponseSerializer)
    def get(self, request, lot_id):
        lot = services.get_lot_for_user(lot_id, request.user)
        return Response({"valid": services.verify_chain(lot)})


class VerifyDetailView(APIView):
    # Public: the farmer opens this from a link without signing in.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "verify"

    @extend_schema(responses=VerifyDataSerializer)
    def get(self, request, token):
        return Response(services.get_verification_data(token))


class VerifyConfirmView(APIView):
    # Public: the farmer opens this from a link without signing in.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "verify"

    @extend_schema(request=None, responses=VerifyActionResponseSerializer)
    def post(self, request, token):
        services.respond_to_verification(token, "confirm")
        return Response({"ok": True, "status": "verified"})


class VerifyDisputeView(APIView):
    # Public: the farmer opens this from a link without signing in.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "verify"

    @extend_schema(request=DisputeRequestSerializer, responses=VerifyActionResponseSerializer)
    def post(self, request, token):
        reason = request.data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError({"reason": ["This field is required."]})
        services.respond_to_verification(token, "dispute", reason.strip())
        return Response({"ok": True, "status": "disputed"})

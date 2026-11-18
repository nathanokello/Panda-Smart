from django.urls import path

from records.views import (
    LotDetailView,
    LotEventsView,
    LotListCreateView,
    MyVerificationLinksView,
    VerifyChainView,
    VerifyConfirmView,
    VerifyDetailView,
    VerifyDisputeView,
)

urlpatterns = [
    path("me/verification-links/", MyVerificationLinksView.as_view(), name="my-verification-links"),
    path("lots/", LotListCreateView.as_view(), name="lot-list"),
    path("lots/<uuid:lot_id>/", LotDetailView.as_view(), name="lot-detail"),
    path("lots/<uuid:lot_id>/events/", LotEventsView.as_view(), name="lot-events"),
    path("lots/<uuid:lot_id>/verify-chain/", VerifyChainView.as_view(), name="lot-verify-chain"),
    path("verify/<str:token>/", VerifyDetailView.as_view(), name="verify-detail"),
    path("verify/<str:token>/confirm/", VerifyConfirmView.as_view(), name="verify-confirm"),
    path("verify/<str:token>/dispute/", VerifyDisputeView.as_view(), name="verify-dispute"),
]

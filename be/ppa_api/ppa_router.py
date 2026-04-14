# PPA API relay router for the frontend.
# Exposes /api/ppa endpoints: health check, player value calculation, and bid recommendation.
# Delegates to PpaAdapterService via FastAPI dependency injection.
from fastapi import APIRouter, Depends, HTTPException

from ppa_api.ppa_schemas import (
    BidRequestIn,
    HealthResponseOut,
    PlayerBidResponseOut,
    PlayerValueResponseOut,
    ValueRequestIn,
)
from ppa_api.ppa_service import PpaAdapterService, PpaServiceError, get_ppa_adapter_service


router = APIRouter(prefix="/api/ppa", tags=["ppa"])


@router.get("/health", response_model=HealthResponseOut)
def get_external_health(
    service: PpaAdapterService = Depends(get_ppa_adapter_service),
):
    try:
        return service.get_health()
    except PpaServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/player/value", response_model=PlayerValueResponseOut)
def calculate_player_value(
    payload: ValueRequestIn,
    service: PpaAdapterService = Depends(get_ppa_adapter_service),
):
    try:
        return service.calculate_player_value(payload)
    except PpaServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/player/bid", response_model=PlayerBidResponseOut)
def calculate_player_bid(
    payload: BidRequestIn,
    service: PpaAdapterService = Depends(get_ppa_adapter_service),
):
    try:
        return service.calculate_player_bid(payload)
    except PpaServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

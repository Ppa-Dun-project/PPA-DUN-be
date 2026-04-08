# 외부 PPA API를 프론트엔드에 중계하는 라우터 모듈.
# /api/ppa 경로 아래에 헬스체크, 선수 가치 계산, 입찰 추천 엔드포인트를 노출한다.
# PpaAdapterService를 DI로 주입받아 요청을 위임하고, 에러를 HTTP 응답으로 변환한다.
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

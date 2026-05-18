# Async HTTP client for the external PPA valuation API.
# Sends requests to /health, /player/bid/id, /players/batters, /players/pitchers
# using httpx.AsyncClient.
# Defines exception classes (HTTP errors, timeouts, invalid responses)
# so the service layer can map them to appropriate HTTP status codes.
import json
import os
from typing import Any, Iterable, Optional

import httpx

############### 오류 클래스 정의 ###############
# 클래스 이름 (상속할 부모 클래스)
# 관례적으로 메세지 하나만 반환하는게 표준이고, 추가적인 정보가 필요한 경우 따로 적음

# 모든 API 관련 오류의 기본 클래스
class ApiError(Exception):
    # Exception의 경우 메세지 문자열 하나를 파라미터로 받는게 전부임
    pass

# API 서버 주소나 API 키가 설정되지 않은 경우 발생시키는 오류
class ApiConfigError(ApiError):
    pass

# HTTP 오류 발생 시 사용하는 클래스 (서버에 도달했고 응답은 받았지만, 응답에 에러)
class ApiHttpError(ApiError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

# 네트워크 오류 발생 시 사용하는 클래스 (서버에 도달 자체가 안됨)
class ApiNetworkError(ApiError):
    def __init__(self, detail: str, timed_out: bool = False):
        super().__init__(detail)
        self.detail = detail
        self.timed_out = timed_out


class ApiInvalidResponseError(ApiError):
    pass


# 외부 API의 에러 응답에서 detail 메시지를 추출하는 함수
def parse_detail(raw_body: str) -> str:
    if not raw_body:
        return "external_api_error"

    # 응답이 JSON인 경우, dict로 전환
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body

    # JSON 형식인데 detail 필드가 있는 경우
    detail = parsed.get("detail")

    # detail이 문자열인 경우 그대로 반환, 그렇지 않으면 원래 응답 본문을 반환
    if isinstance(detail, str):
        return detail

    return raw_body


############# 외부 API에 실제로 보낼 HTTP 요청 생성 ##############
class PpaApiClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float):
        # 외부 API 서버 주소
        self._base_url = base_url.rstrip("/")
        # 인증 키
        self._api_key = api_key
        # 요청 타임아웃 시간
        self._timeout_seconds = timeout_seconds
        # 공유 httpx 클라이언트. async with 컨텍스트로 진입 시 한 번 생성되어 모든 요청에서
        # connection pool을 공유. 컨텍스트 밖 호출은 매 요청마다 ephemeral 클라이언트 사용.
        self._shared_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "PpaApiClient":
        self._shared_client = httpx.AsyncClient(timeout=self._timeout_seconds)
        return self

    async def __aexit__(self, *_exc_info) -> None:
        if self._shared_client is not None:
            await self._shared_client.aclose()
            self._shared_client = None

    # 서버 살아있는지 확인
    async def health(self) -> dict[str, Any]:
        return await self.request_json("GET", "/health", body=None, requires_auth=False)

    # 야구 선수 입찰가 추천. payload 형식은 호출자 책임.
    # 신규 스펙: {player_id, league_context, draft_context: {..., my_positions_filled}}
    async def player_bid(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_json("POST", "/player/bid/id", body=payload, requires_auth=True)

    # 리그 전체 선수 목록 + valuation score 조회
    # league는 "AL" 또는 "NL", columns는 반환받을 필드 이름 리스트 (None이면 API 기본값 사용)
    async def _players_by_league(
        self,
        path: str,
        league: str,
        columns: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        # 쿼리 파라미터 구성: league는 필수, columns는 선택
        query_params: dict[str, str] = {"league": league}

        if columns is not None:
            # API 명세상 columns는 콤마 구분 문자열로 전달
            query_params["columns"] = ",".join(columns)

        return await self.request_json(
            "GET",
            path,
            body=None,
            requires_auth=True,
            query_params=query_params,
        )

    async def batters_by_league(
        self,
        league: str,
        columns: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        return await self._players_by_league("/players/batters", league, columns)

    async def pitchers_by_league(
        self,
        league: str,
        columns: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        return await self._players_by_league("/players/pitchers", league, columns)

    ############## HTTP 요청을 보내고 응답 받는 형식 생성 ###############
    # API 서버와 주고 받을 형식 구상, 요청 전송 및 응답 처리
    async def request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        requires_auth: bool,
        query_params: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:

        # API의 서버 주소가 비어있는 경우 오류 처리
        if not self._base_url:
            raise ApiConfigError("EXTERNAL_API_BASE_URL is not configured")

        # HTTP 요청에 붙일 헤더: 응답을 JSON으로 받겠다고 명시.
        headers: dict[str, str] = {"Accept": "application/json"}

        # 인증이 필요한 경우, API키가 없으면 오류 처리. API 키를 헤더에 추가
        if requires_auth:
            if not self._api_key:
                raise ApiConfigError("EXTERNAL_API_KEY is not configured")
            headers["X-API-Key"] = self._api_key

        url = f"{self._base_url}{path}"

        try:
            # 컨텍스트 매니저로 열린 공유 클라이언트가 있으면 재사용 (대량 동시 호출 시 connection pool 활용),
            # 없으면 ephemeral 클라이언트를 매 호출마다 생성 (단발성 호출용).
            if self._shared_client is not None:
                response = await self._shared_client.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=body,
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=query_params,
                        json=body,
                        headers=headers,
                    )
        # 타임아웃 (연결/읽기 등 모든 타임아웃 포괄)
        except httpx.TimeoutException as exc:
            raise ApiNetworkError(detail="External API request timed out", timed_out=True) from exc
        # 그 외 네트워크 레벨 오류 (DNS 실패, 연결 거부 등)
        except httpx.RequestError as exc:
            raise ApiNetworkError(detail=str(exc) or "Failed to reach external API") from exc

        # 4xx/5xx 응답: 본문에서 detail 추출 후 ApiHttpError 발생
        if response.is_error:
            raw_error = response.text
            raise ApiHttpError(response.status_code, parse_detail(raw_error))

        raw_body = response.text

        # 응답이 비어있는 경우 처리
        if not raw_body:
            return {}

        # JSON 형식의 응답을 딕셔너리로 파싱
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ApiInvalidResponseError("External API returned invalid JSON") from exc

        # 응답이 JSON 객체가 아닌 경우 오류 처리 (JSON 배열이나 단일 값 등)
        if not isinstance(parsed, dict):
            raise ApiInvalidResponseError("External API response is not a JSON object")

        return parsed


# 환경 변수 기반 기본 클라이언트 인스턴스 생성 팩토리.
def build_ppa_api_client() -> PpaApiClient:
    return PpaApiClient(
        base_url=os.getenv("EXTERNAL_API_BASE_URL", ""),
        api_key=os.getenv("EXTERNAL_API_KEY", ""),
        timeout_seconds=float(os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "5")),
    )

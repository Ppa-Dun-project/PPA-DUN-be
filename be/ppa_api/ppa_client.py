# Low-level HTTP client for the external PPA valuation API.
# Sends requests to /health, /player/value, and /player/bid using urllib.
# Defines exception classes (HTTP errors, timeouts, invalid responses)
# so the service layer can map them to appropriate HTTP status codes.
import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

    # 서버 살아있는지 확인
    def health(self) -> dict[str, Any]:
        return self.request_json("GET", "/health", body=None, requires_auth=False)
    
    # 야구 선수 가치 계산
    # body에 선수 정보, 리그 정보, 시즌 정보 등을 담아서 POST 요청을 보낸다.
    def player_value(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/player/value", body=payload, requires_auth=True)

    # 야구 선수 입찰가 추천
    # body에 위와 동일한 정보를 넣어서 보낸다
    def player_bid(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/player/bid", body=payload, requires_auth=True)


    ############## HTTP 요청을 보내고 응답 받는 형식 생성 ###############
    # API 서버와 주고 받을 형식 구상, 요청 전송 및 응답 처리
    def request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        requires_auth: bool,
    ) -> dict[str, Any]:
        
        # API의 서버 주소가 비어있는 경우 오류 처리
        if not self._base_url:
            raise ApiConfigError("EXTERNAL_API_BASE_URL is not configured")

        # HTTP 요청에 붙일 헤더: 응답을 JSON으로 받겠다고 명시.
        # 딕셔너리 타입의 헤더 선언 후 "Accept: application/json" 추가
        headers: dict[str, str] = {"Accept": "application/json"}
        
        # HTTP 요청에 붙여 본문 내용을 담아 보낼 변수 선언 
        data: bytes | None = None

        # POST 요청 / GET 요청의 경우 보내는 body가 따로 없음
        if body is not None:
            
            # API에게 보낼 데이터 타입이 JSON임을 명시하는 헤더
            headers["Content-Type"] = "application/json"
            
            # body 딕셔너리를 JSON 문자열로 변환한 뒤, UTF-8 인코딩을 거쳐 bytes 타입으로 변환하여 data 변수에 저장
            data = json.dumps(body).encode("utf-8")

        
        
        # 인증이 필요한 경우, API키가 없으면 오류 처리. API 키를 헤더에 추가
        if requires_auth:
            if not self._api_key:
                raise ApiConfigError("EXTERNAL_API_KEY is not configured")
            # 헤더 딕셔너리에 API 키 추가
            headers["X-API-Key"] = self._api_key

        # API로 보낼 요청 데이터 생성
        request = Request(
            url=f"{self._base_url}{path}", # 요청을 보낼 URL: base_url과 path를 합쳐서 완성
            data=data, # POST와 GET에 맞는 요청 본문 
            headers=headers, # 위 조건에 맞게 생성된 헤더
            method=method, # HTTP 메서드 (GET, POST 등)
        )

        try:
            # 요청을 보내고, 타임아웃 에러 설정
            # with를 이용하여 return이 끝날때 연결이 자동으로 닫히도록 설정
            with urlopen(request, timeout=self._timeout_seconds) as response:
                
                # Read response body from API, byte -> string
                raw_body = response.read().decode("utf-8")
                
                # 응답이 비어있는 경우 처리
                if not raw_body:
                    return {}
                
                # JSON 형식의 응답을 딕셔너리로 파싱
                parsed = json.loads(raw_body)
                
                # 응답이 JSON 객체가 아닌 경우 오류 처리 (JSON 배열이나 단일 값 등)
                if not isinstance(parsed, dict):
                    raise ApiInvalidResponseError("External API response is not a JSON object")
                
                # 파싱된 응답 반환
                return parsed
        
        # API가 응답을 했지만 body에 에러가 있는 경우
        except HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            raise ApiHttpError(exc.code, parse_detail(raw_error)) from exc
        
        # API 서버에 연결 자체가 실패한 경우
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            is_timeout = isinstance(reason, socket.timeout)
            detail = str(reason) if reason is not None else "Failed to reach external API"
            raise ApiNetworkError(detail=detail, timed_out=is_timeout) from exc
        
        # API 타임아웃 오류 발생 (Python 버전에 따라 두가지로 나뉘어 오므로 두개 모두 처리)
        except socket.timeout as exc:
            raise ApiNetworkError(detail="External API request timed out", timed_out=True) from exc
        except TimeoutError as exc:
            raise ApiNetworkError(detail="External API request timed out", timed_out=True) from exc
        
        # 응답이 유효한 JSON이 아닌 경우 (HTML 또는 깨진 텍스트 등)
        except json.JSONDecodeError as exc:
            raise ApiInvalidResponseError("External API returned invalid JSON") from exc

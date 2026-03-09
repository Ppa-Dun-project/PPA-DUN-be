import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ExternalApiError(Exception):
    pass


class ExternalApiConfigError(ExternalApiError):
    pass


class ExternalApiHttpError(ExternalApiError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ExternalApiNetworkError(ExternalApiError):
    def __init__(self, detail: str, timed_out: bool = False):
        super().__init__(detail)
        self.detail = detail
        self.timed_out = timed_out


class ExternalApiInvalidResponseError(ExternalApiError):
    pass


def _parse_detail(raw_body: str) -> str:
    if not raw_body:
        return "external_api_error"
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body

    detail = parsed.get("detail")
    if isinstance(detail, str):
        return detail
    return raw_body


class PpaExternalApiClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health", body=None, requires_auth=False)

    def player_value(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", "/player/value", body=payload, requires_auth=True)

    def player_bid(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", "/player/bid", body=payload, requires_auth=True)

    def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        requires_auth: bool,
    ) -> dict[str, Any]:
        if not self._base_url:
            raise ExternalApiConfigError("EXTERNAL_API_BASE_URL is not configured")

        headers: dict[str, str] = {"Accept": "application/json"}
        data: bytes | None = None

        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        if requires_auth:
            if not self._api_key:
                raise ExternalApiConfigError("EXTERNAL_API_KEY is not configured")
            headers["X-API-Key"] = self._api_key

        request = Request(
            url=f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )

        try:
            # API 호출 지점
            with urlopen(request, timeout=self._timeout_seconds) as response:
                
                # API에서 본문 수신 하는 지점
                raw_body = response.read().decode("utf-8")
                if not raw_body:
                    return {}
                
                parsed = json.loads(raw_body)
                print(parsed)
                if not isinstance(parsed, dict):
                    raise ExternalApiInvalidResponseError("External API response is not a JSON object")
                return parsed
            
        except HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            raise ExternalApiHttpError(exc.code, _parse_detail(raw_error)) from exc
        
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            is_timeout = isinstance(reason, socket.timeout)
            detail = str(reason) if reason is not None else "Failed to reach external API"
            raise ExternalApiNetworkError(detail=detail, timed_out=is_timeout) from exc
        
        except socket.timeout as exc:
            raise ExternalApiNetworkError(detail="External API request timed out", timed_out=True) from exc
        
        except TimeoutError as exc:
            raise ExternalApiNetworkError(detail="External API request timed out", timed_out=True) from exc
        
        except json.JSONDecodeError as exc:
            raise ExternalApiInvalidResponseError("External API returned invalid JSON") from exc

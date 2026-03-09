from pydantic import ValidationError

from core.config import settings
from ppa_client import (
    ExternalApiConfigError,
    ExternalApiHttpError,
    ExternalApiInvalidResponseError,
    ExternalApiNetworkError,
    PpaExternalApiClient,
)
from ppa_schemas import (
    BidRequestIn,
    HealthResponseOut,
    PlayerBidResponseOut,
    PlayerValueResponseOut,
    ValueRequestIn,
    build_bid_payload,
    build_value_payload,
    map_bid_response,
    map_health_response,
    map_value_response,
)


class PpaServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class PpaAdapterService:
    def __init__(self, client: PpaExternalApiClient):
        self._client = client

    @classmethod
    def from_settings(cls) -> "PpaAdapterService":
        client = PpaExternalApiClient(
            base_url=settings.EXTERNAL_API_BASE_URL,
            api_key=settings.EXTERNAL_API_KEY,
            timeout_seconds=settings.EXTERNAL_API_TIMEOUT_SECONDS,
        )
        return cls(client=client)

    def get_health(self) -> HealthResponseOut:
        try:
            raw = self._client.health()
            return map_health_response(raw)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PpaServiceError(502, "External health response format is invalid") from exc
        except (
            ExternalApiConfigError,
            ExternalApiHttpError,
            ExternalApiNetworkError,
            ExternalApiInvalidResponseError,
        ) as exc:
            raise self._map_external_error(exc) from exc

    def calculate_player_value(self, payload: ValueRequestIn) -> PlayerValueResponseOut:
        external_payload = build_value_payload(payload)
        try:
            raw = self._client.player_value(external_payload)
            return map_value_response(raw)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PpaServiceError(502, "External value response format is invalid") from exc
        except (
            ExternalApiConfigError,
            ExternalApiHttpError,
            ExternalApiNetworkError,
            ExternalApiInvalidResponseError,
        ) as exc:
            raise self._map_external_error(exc) from exc

    def calculate_player_bid(self, payload: BidRequestIn) -> PlayerBidResponseOut:
        external_payload = build_bid_payload(payload)
        try:
            raw = self._client.player_bid(external_payload)
        except ExternalApiNetworkError as exc:
            if not exc.timed_out:
                raise self._map_external_error(exc) from exc
            try:
                raw = self._client.player_bid(external_payload)
            except (
                ExternalApiConfigError,
                ExternalApiHttpError,
                ExternalApiNetworkError,
                ExternalApiInvalidResponseError,
            ) as retry_exc:
                raise self._map_external_error(retry_exc) from retry_exc
        except (
            ExternalApiConfigError,
            ExternalApiHttpError,
            ExternalApiInvalidResponseError,
        ) as exc:
            raise self._map_external_error(exc) from exc

        try:
            return map_bid_response(raw)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PpaServiceError(502, "External bid response format is invalid") from exc

    def _map_external_error(self, error: Exception) -> PpaServiceError:
        if isinstance(error, ExternalApiConfigError):
            return PpaServiceError(500, "External valuation service is not configured")

        if isinstance(error, ExternalApiNetworkError):
            if error.timed_out:
                return PpaServiceError(504, "External valuation service request timed out")
            return PpaServiceError(503, "External valuation service is unreachable")

        if isinstance(error, ExternalApiInvalidResponseError):
            return PpaServiceError(502, "External valuation service returned invalid JSON")

        if isinstance(error, ExternalApiHttpError):
            if error.status_code == 401:
                return PpaServiceError(502, "External valuation service authentication failed")
            if error.status_code == 422:
                return PpaServiceError(
                    400,
                    f"External valuation request validation failed: {error.detail}",
                )
            if 400 <= error.status_code < 500:
                return PpaServiceError(
                    502,
                    f"External valuation request failed with status {error.status_code}",
                )
            return PpaServiceError(502, "External valuation service error")

        return PpaServiceError(500, "Unexpected adapter error")


def get_ppa_adapter_service() -> PpaAdapterService:
    return PpaAdapterService.from_settings()

# Integration test for PpaApiClient — verifies the BE ↔ external API server
# communication contract. The bid endpoint (POST /player/bid/id), batter
# listing (GET /players/batters), and pitcher listing (GET /players/pitchers)
# are all owned by the external PPA API; this test pins down the HTTP-level
# behaviour the BE relies on:
#   - URL construction (base_url + path + query params)
#   - X-API-Key auth header on protected routes (and absence on /health)
#   - Accept: application/json header
#   - JSON body serialization for POST
#   - Response parsing (success, empty body, malformed JSON)
#   - Error mapping (HTTP 4xx/5xx → ApiHttpError, timeout → ApiNetworkError
#     with timed_out=True, network failure → ApiNetworkError, missing config
#     → ApiConfigError)
#
# The external API server is simulated with httpx.MockTransport so no real
# network call is made — the BE's HTTP layer is exercised end-to-end against
# a controllable counterpart.
import json

import httpx
import pytest

from ppa_api.ppa_client import (
    ApiConfigError,
    ApiHttpError,
    ApiInvalidResponseError,
    ApiNetworkError,
    PpaApiClient,
)


BASE_URL = "https://api.test.local"
API_KEY = "test-api-key"


def _client_with_transport(transport: httpx.MockTransport) -> PpaApiClient:
    """Builds a PpaApiClient whose shared httpx.AsyncClient routes through the
    given MockTransport. Mirrors what `async with build_ppa_api_client()` does
    in production, but with a stub transport substituted for the real network."""
    client = PpaApiClient(base_url=BASE_URL, api_key=API_KEY, timeout_seconds=2.0)
    client._shared_client = httpx.AsyncClient(transport=transport, timeout=2.0)
    return client


async def _close(client: PpaApiClient) -> None:
    if client._shared_client is not None:
        await client._shared_client.aclose()
        client._shared_client = None


# ── happy-path: contract between BE and the API server ──────────────────────

@pytest.mark.asyncio
async def test_player_bid_sends_auth_header_and_json_body():
    # POST /player/bid/id must carry the API key, JSON body, and exact URL the external API expects.
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"recommended_bid": 42})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        payload = {
            "player_id": 12345,
            "league_context": {"league_size": 10, "roster_size": 23, "total_budget": 260},
            "draft_context": {
                "my_remaining_budget": 200,
                "my_remaining_roster_spots": 20,
                "drafted_players_count": 5,
                "my_positions_filled": ["C", "1B"],
            },
        }
        result = await client.player_bid(payload)
    finally:
        await _close(client)

    assert result == {"recommended_bid": 42}
    assert captured["method"] == "POST"
    assert captured["url"] == f"{BASE_URL}/player/bid/id"
    assert captured["headers"]["x-api-key"] == API_KEY
    assert captured["headers"]["accept"] == "application/json"
    assert captured["body"] == payload


@pytest.mark.asyncio
async def test_batters_by_league_sends_query_params_and_auth():
    # GET /players/batters must encode league + columns as query params with the API key attached.
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"items": []})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await client.batters_by_league("NL", columns=["player_id", "name", "avg"])
    finally:
        await _close(client)

    assert captured["url"].startswith(f"{BASE_URL}/players/batters")
    assert captured["params"]["league"] == "NL"
    assert captured["params"]["columns"] == "player_id,name,avg"
    assert captured["headers"]["x-api-key"] == API_KEY


@pytest.mark.asyncio
async def test_health_check_skips_auth_header():
    # GET /health is unauthenticated — the client must not attach the API key.
    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"status": "ok"})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        result = await client.health()
    finally:
        await _close(client)

    assert result == {"status": "ok"}
    assert "x-api-key" not in captured_headers


# ── error mapping: protocol failures must surface as typed exceptions ───────

@pytest.mark.asyncio
async def test_http_error_response_raises_api_http_error_with_detail():
    # A 4xx/5xx response must surface as ApiHttpError with status + parsed detail preserved.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "player not found"})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiHttpError) as exc_info:
            await client.player_bid({"player_id": 1})
    finally:
        await _close(client)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "player not found"


@pytest.mark.asyncio
async def test_timeout_raises_network_error_with_timed_out_flag():
    # A request timeout must map to ApiNetworkError with the timed_out flag set so the caller can distinguish.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out")

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiNetworkError) as exc_info:
            await client.player_bid({"player_id": 1})
    finally:
        await _close(client)

    assert exc_info.value.timed_out is True


@pytest.mark.asyncio
async def test_connection_failure_raises_network_error_without_timeout_flag():
    # Non-timeout network failure must map to ApiNetworkError with timed_out=False.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiNetworkError) as exc_info:
            await client.player_bid({"player_id": 1})
    finally:
        await _close(client)

    assert exc_info.value.timed_out is False


@pytest.mark.asyncio
async def test_malformed_json_response_raises_invalid_response_error():
    # Non-JSON response body must raise ApiInvalidResponseError instead of leaking a parse error.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json {{")

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiInvalidResponseError):
            await client.player_bid({"player_id": 1})
    finally:
        await _close(client)


@pytest.mark.asyncio
async def test_non_object_json_response_raises_invalid_response_error():
    # A JSON value that is not an object (e.g. an array) violates the API contract and must raise.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["this", "is", "not", "an", "object"])

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiInvalidResponseError):
            await client.player_bid({"player_id": 1})
    finally:
        await _close(client)


@pytest.mark.asyncio
async def test_empty_response_body_returns_empty_dict():
    # An empty 200 body must be coerced to an empty dict instead of raising on parse.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        result = await client.player_bid({"player_id": 1})
    finally:
        await _close(client)

    assert result == {}


@pytest.mark.asyncio
async def test_missing_base_url_raises_config_error():
    # Missing EXTERNAL_API_BASE_URL must fail fast with ApiConfigError before any HTTP attempt.
    client = PpaApiClient(base_url="", api_key=API_KEY, timeout_seconds=2.0)
    with pytest.raises(ApiConfigError):
        await client.health()


@pytest.mark.asyncio
async def test_missing_api_key_on_protected_route_raises_config_error():
    # Missing EXTERNAL_API_KEY on an authed route must fail fast instead of sending an unauthenticated request.
    client = PpaApiClient(base_url=BASE_URL, api_key="", timeout_seconds=2.0)
    with pytest.raises(ApiConfigError):
        await client.player_bid({"player_id": 1})

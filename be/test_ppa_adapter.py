import unittest

from fastapi.testclient import TestClient

import main
from ppa_client import ExternalApiHttpError, ExternalApiNetworkError
from ppa_schemas import BatterBidRequestIn, BatterValueRequestIn
from ppa_service import PpaAdapterService, PpaServiceError, get_ppa_adapter_service


def build_batter_value_payload() -> dict:
    return {
        "playerName": "Aaron Judge",
        "playerType": "batter",
        "position": "LF",
        "stats": {
            "AB": 559,
            "R": 122,
            "HR": 58,
            "RBI": 144,
            "SB": 10,
            "CS": 3,
            "AVG": 0.322,
        },
        "leagueContext": {
            "leagueSize": 12,
            "rosterSize": 23,
            "totalBudget": 3120,
        },
    }


def build_pitcher_value_payload() -> dict:
    return {
        "playerName": "Gerrit Cole",
        "playerType": "pitcher",
        "position": "SP",
        "stats": {
            "IP": 200.1,
            "W": 17,
            "SV": 0,
            "K": 245,
            "ERA": 2.89,
            "WHIP": 1.01,
        },
        "leagueContext": {
            "leagueSize": 12,
            "rosterSize": 23,
            "totalBudget": 3120,
        },
    }


def build_batter_bid_payload() -> dict:
    payload = build_batter_value_payload()
    payload["draftContext"] = {
        "myRemainingBudget": 120,
        "myRemainingRosterSpots": 6,
        "myPositionsFilled": ["C", "1B", "cf"],
        "draftedPlayersCount": 17,
    }
    return payload


class StubPpaService:
    def __init__(self):
        self.raise_error: PpaServiceError | None = None

    def get_health(self):
        if self.raise_error:
            raise self.raise_error
        return {"status": "ok"}

    def calculate_player_value(self, payload):
        if self.raise_error:
            raise self.raise_error
        return {
            "playerName": payload.playerName,
            "playerType": payload.playerType,
            "playerValue": 41.5,
            "valueBreakdown": {
                "statScore": 39.0,
                "positionBonus": 4.0,
                "riskPenalty": -1.5,
            },
        }

    def calculate_player_bid(self, payload):
        if self.raise_error:
            raise self.raise_error
        return {
            "playerName": payload.playerName,
            "playerType": payload.playerType,
            "playerValue": 41.5,
            "recommendedBid": 39,
            "bidBreakdown": {
                "basePrice": 34.0,
                "scarcityAdjustment": 2.5,
                "draftAdjustment": 2.0,
                "maxSpendable": 45,
            },
        }


class PpaRouterTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.stub = StubPpaService()
        main.app.dependency_overrides[get_ppa_adapter_service] = lambda: self.stub

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_health_check_success(self):
        response = self.client.get("/api/ppa/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_batter_value_success(self):
        response = self.client.post("/api/ppa/player/value", json=build_batter_value_payload())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["playerType"], "batter")
        self.assertEqual(body["playerName"], "Aaron Judge")

    def test_pitcher_value_success(self):
        response = self.client.post("/api/ppa/player/value", json=build_pitcher_value_payload())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["playerType"], "pitcher")
        self.assertEqual(body["playerName"], "Gerrit Cole")

    def test_batter_bid_success(self):
        response = self.client.post("/api/ppa/player/bid", json=build_batter_bid_payload())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["recommendedBid"], 39)
        self.assertEqual(body["playerType"], "batter")

    def test_draft_context_validation_fail(self):
        payload = build_batter_bid_payload()
        payload["draftContext"]["myRemainingRosterSpots"] = 0
        response = self.client.post("/api/ppa/player/bid", json=payload)
        self.assertEqual(response.status_code, 422)


class PpaServiceErrorMappingTest(unittest.TestCase):
    def test_external_401_maps_to_502(self):
        class Client401:
            def player_value(self, payload):
                raise ExternalApiHttpError(401, "invalid_api_key")

        service = PpaAdapterService(client=Client401())
        payload = BatterValueRequestIn(**build_batter_value_payload())
        with self.assertRaises(PpaServiceError) as ctx:
            service.calculate_player_value(payload)

        self.assertEqual(ctx.exception.status_code, 502)

    def test_external_422_maps_to_400(self):
        class Client422:
            def player_value(self, payload):
                raise ExternalApiHttpError(422, "validation_error")

        service = PpaAdapterService(client=Client422())
        payload = BatterValueRequestIn(**build_batter_value_payload())
        with self.assertRaises(PpaServiceError) as ctx:
            service.calculate_player_value(payload)

        self.assertEqual(ctx.exception.status_code, 400)

    def test_external_timeout_maps_to_504(self):
        class TimeoutClient:
            def player_value(self, payload):
                raise ExternalApiNetworkError("timeout", timed_out=True)

        service = PpaAdapterService(client=TimeoutClient())
        payload = BatterValueRequestIn(**build_batter_value_payload())
        with self.assertRaises(PpaServiceError) as ctx:
            service.calculate_player_value(payload)

        self.assertEqual(ctx.exception.status_code, 504)

    def test_bid_timeout_retries_once(self):
        class TimeoutThenSuccessClient:
            def __init__(self):
                self.calls = 0

            def player_bid(self, payload):
                self.calls += 1
                if self.calls == 1:
                    raise ExternalApiNetworkError("timeout", timed_out=True)
                return {
                    "player_name": "Aaron Judge",
                    "player_type": "batter",
                    "player_value": 41.5,
                    "recommended_bid": 42,
                    "bid_breakdown": {
                        "base_price": 34.0,
                        "scarcity_adjustment": 2.5,
                        "draft_adjustment": 2.0,
                        "max_spendable": 45,
                    },
                }

        client = TimeoutThenSuccessClient()
        service = PpaAdapterService(client=client)
        payload = BatterBidRequestIn(**build_batter_bid_payload())
        result = service.calculate_player_bid(payload)

        self.assertEqual(result.recommendedBid, 42)
        self.assertEqual(client.calls, 2)


if __name__ == "__main__":
    unittest.main()

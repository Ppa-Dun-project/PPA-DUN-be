import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

import draft
import main
from core.config import settings
from ppa_service import PpaServiceError, get_ppa_adapter_service


class StubBidService:
    def __init__(self):
        self.raise_error: PpaServiceError | None = None
        self.calls = 0

    def calculate_player_bid(self, payload):
        self.calls += 1
        if self.raise_error:
            raise self.raise_error
        return SimpleNamespace(recommendedBid=77, playerValue=88.5)


class DraftBidRecommendationTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.stub = StubBidService()
        main.app.dependency_overrides[get_ppa_adapter_service] = lambda: self.stub
        draft.PLAYER_MARKET_CACHE.clear()
        draft.DRAFT_PICKS_BY_ROOM["default"] = []

        self.prev_base_url = settings.EXTERNAL_API_BASE_URL
        self.prev_api_key = settings.EXTERNAL_API_KEY
        settings.EXTERNAL_API_BASE_URL = "http://example.local"
        settings.EXTERNAL_API_KEY = "test-key"

    def tearDown(self):
        settings.EXTERNAL_API_BASE_URL = self.prev_base_url
        settings.EXTERNAL_API_KEY = self.prev_api_key
        main.app.dependency_overrides.clear()

    def test_players_endpoint_uses_external_recommended_bid(self):
        response = self.client.get("/api/draft/players", params={"query": "Shohei", "limit": 1})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"][0]["recommendedBid"], 77)
        self.assertEqual(body["items"][0]["ppaValue"], 88.5)
        self.assertGreaterEqual(self.stub.calls, 1)

    def test_players_endpoint_falls_back_when_external_api_fails(self):
        self.stub.raise_error = PpaServiceError(503, "downstream unavailable")
        response = self.client.get("/api/draft/players", params={"query": "Shohei", "limit": 1})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"][0]["recommendedBid"], 52)
        self.assertEqual(body["items"][0]["ppaValue"], 99.2)

    def test_players_endpoint_calls_external_for_page_items_only(self):
        response = self.client.get("/api/draft/players", params={"limit": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 3)
        self.assertEqual(self.stub.calls, 3)


if __name__ == "__main__":
    unittest.main()

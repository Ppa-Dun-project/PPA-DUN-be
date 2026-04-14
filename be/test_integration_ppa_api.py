# Integration test: verifies value/bid responses against the real PPA API server.
# Requires the PPA API server to be running.
# Tests are automatically skipped if the API server is unavailable.
import unittest

from fastapi.testclient import TestClient

import main
from ppa_api.ppa_service import PpaAdapterService, PpaServiceError


def _is_ppa_api_available() -> bool:
    """Check if the PPA API server is responding."""
    try:
        service = PpaAdapterService.from_settings()
        service.get_health()
        return True
    except Exception:
        return False


@unittest.skipUnless(_is_ppa_api_available(), "PPA API server is not running")
class PpaValueBidFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_batter_value_returns_required_fields(self):
        payload = {
            "playerName": "Aaron Judge",
            "playerType": "batter",
            "position": "OF",
            "stats": {
                "AB": 550, "R": 120, "HR": 53, "RBI": 114,
                "SB": 12, "CS": 3, "AVG": 0.331,
            },
            "leagueContext": {
                "leagueSize": 12, "rosterSize": 23, "totalBudget": 3120,
            },
        }
        resp = self.client.post("/api/ppa/player/value", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("playerValue", body)
        self.assertIn("valueBreakdown", body)
        self.assertIsInstance(body["playerValue"], (int, float))
        self.assertGreater(body["playerValue"], 0)

    def test_pitcher_value_returns_required_fields(self):
        payload = {
            "playerName": "Gerrit Cole",
            "playerType": "pitcher",
            "position": "SP",
            "stats": {
                "IP": 200.1, "W": 17, "SV": 0,
                "K": 245, "ERA": 2.89, "WHIP": 1.01,
            },
            "leagueContext": {
                "leagueSize": 12, "rosterSize": 23, "totalBudget": 3120,
            },
        }
        resp = self.client.post("/api/ppa/player/value", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("playerValue", body)
        self.assertGreater(body["playerValue"], 0)

    def test_batter_bid_returns_recommended_bid(self):
        payload = {
            "playerName": "Aaron Judge",
            "playerType": "batter",
            "position": "OF",
            "stats": {
                "AB": 550, "R": 120, "HR": 53, "RBI": 114,
                "SB": 12, "CS": 3, "AVG": 0.331,
            },
            "leagueContext": {
                "leagueSize": 12, "rosterSize": 23, "totalBudget": 3120,
            },
            "draftContext": {
                "myRemainingBudget": 200,
                "myRemainingRosterSpots": 15,
                "myPositionsFilled": ["C", "1B"],
                "draftedPlayersCount": 8,
            },
        }
        resp = self.client.post("/api/ppa/player/bid", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("recommendedBid", body)
        self.assertIn("playerValue", body)
        self.assertIn("bidBreakdown", body)
        self.assertIsInstance(body["recommendedBid"], int)
        self.assertGreater(body["recommendedBid"], 0)

    def test_invalid_payload_returns_422(self):
        payload = {
            "playerName": "Aaron Judge",
            "playerType": "batter",
            "position": "OF",
            "stats": {"AB": 550},
            "leagueContext": {
                "leagueSize": 12, "rosterSize": 23, "totalBudget": 3120,
            },
        }
        resp = self.client.post("/api/ppa/player/value", json=payload)
        self.assertEqual(resp.status_code, 422)

    def test_bid_with_zero_roster_spots_returns_422(self):
        payload = {
            "playerName": "Aaron Judge",
            "playerType": "batter",
            "position": "OF",
            "stats": {
                "AB": 550, "R": 120, "HR": 53, "RBI": 114,
                "SB": 12, "CS": 3, "AVG": 0.331,
            },
            "leagueContext": {
                "leagueSize": 12, "rosterSize": 23, "totalBudget": 3120,
            },
            "draftContext": {
                "myRemainingBudget": 200,
                "myRemainingRosterSpots": 0,
                "myPositionsFilled": [],
                "draftedPlayersCount": 0,
            },
        }
        resp = self.client.post("/api/ppa/player/bid", json=payload)
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()

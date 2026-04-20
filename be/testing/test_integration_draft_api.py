# Integration test: verifies draft pick lifecycle with real DB state.
# No stubs. Tests sequential pick registration, duplicate handling,
# deletion, and budget reflection against the actual database.
import unittest

from fastapi.testclient import TestClient

import main
from database.draft_store import reset_draft, load_draft_picks


class DraftPickLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.user_id = "test-integration-lifecycle"
        reset_draft(self.user_id)

    def tearDown(self):
        reset_draft(self.user_id)

    def test_sequential_picks_accumulate(self):
        # Register first pick
        resp1 = self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "592450",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 44,
                "type": "mine",
            },
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(len(resp1.json()["items"]), 1)

        # Register second pick
        resp2 = self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "665742",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 39,
                "type": "mine",
            },
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.json()["items"]), 2)

        # Verify 2 picks are persisted in DB
        db_picks = load_draft_picks(self.user_id)
        self.assertEqual(len(db_picks), 2)

    def test_duplicate_player_pick_updates_existing(self):
        # Registering the same player twice should upsert (update existing)
        self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "592450",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 30,
                "type": "mine",
            },
        )
        resp = self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "592450",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 50,
                "type": "mine",
            },
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        matching = [p for p in items if p["playerId"] == "592450"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["bid"], 50)

    def test_delete_pick_removes_from_db(self):
        # Register then delete a pick
        self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "592450",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 44,
                "type": "mine",
            },
        )
        resp = self.client.delete(
            "/api/draft/picks/592450",
            params={"userId": self.user_id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["items"]), 0)

        # Verify pick is also removed from DB
        db_picks = load_draft_picks(self.user_id)
        self.assertEqual(len(db_picks), 0)

    def test_delete_nonexistent_pick_returns_404(self):
        resp = self.client.delete(
            "/api/draft/picks/999999",
            params={"userId": self.user_id},
        )
        self.assertEqual(resp.status_code, 404)

    def test_budget_reflected_in_picks(self):
        # Verify bid values are correctly persisted
        self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "592450",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 44,
                "type": "mine",
            },
        )
        self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 23},
            json={
                "playerId": "665742",
                "draftedByTeamId": "team-0",
                "slotPos": "OF",
                "bid": 39,
                "type": "mine",
            },
        )
        resp = self.client.get(
            "/api/draft/picks",
            params={"userId": self.user_id},
        )
        items = resp.json()["items"]
        total_spent = sum(p["bid"] for p in items if p["bid"] is not None)
        self.assertEqual(total_spent, 83)


if __name__ == "__main__":
    unittest.main()

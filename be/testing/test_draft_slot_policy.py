# Unit test: verifies draft pick slot assignment policy.
# Picks are assigned to the first open slot regardless of position,
# and a 409 error is returned when the roster is full.
import unittest

from fastapi.testclient import TestClient

import draft
import main
from database.draft_store import reset_draft


class DraftSlotPolicyTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.user_id = "test-slot-policy"
        reset_draft(self.user_id)
        draft.clear_user_caches(self.user_id)

    def tearDown(self):
        reset_draft(self.user_id)
        draft.clear_user_caches(self.user_id)

    def test_position_is_ignored_and_first_open_slot_is_used(self):
        response = self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 12},
            json={
                "playerId": "592450",
                "draftedByTeamId": "team-0",
                "slotPos": "C",
                "bid": 21,
                "type": "mine",
            },
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["slotIndex"], 0)
        self.assertEqual(item["slotPos"], "SP")

    def test_conflict_when_team_roster_is_full(self):
        # Must use real player_ids that exist in the DB
        player_ids = [str(660271 + i) for i in range(12)]
        for player_id in player_ids:
            response = self.client.post(
                "/api/draft/picks",
                params={"userId": self.user_id, "rosterPlayers": 12},
                json={
                    "playerId": player_id,
                    "draftedByTeamId": "team-0",
                    "slotPos": "C",
                    "bid": 1,
                    "type": "mine",
                },
            )
            if response.status_code != 200:
                break

        overflow = self.client.post(
            "/api/draft/picks",
            params={"userId": self.user_id, "rosterPlayers": 12},
            json={
                "playerId": "999999",
                "draftedByTeamId": "team-0",
                "slotPos": "C",
                "bid": 1,
                "type": "mine",
            },
        )
        self.assertEqual(overflow.status_code, 409)
        self.assertEqual(overflow.json()["detail"], "No available slot for team roster")


if __name__ == "__main__":
    unittest.main()

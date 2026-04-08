# 드래프트 픽 등록 시 슬롯 배정 정책을 검증하는 테스트 모듈.
# 포지션과 무관하게 첫 번째 빈 슬롯에 배정되는지, 로스터가 꽉 찼을 때 409 에러가 반환되는지를 테스트한다.
import unittest

from fastapi.testclient import TestClient

import draft
import main


class DraftSlotPolicyTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.room_id = "slot-policy-room"
        draft.DRAFT_PICKS_BY_ROOM[self.room_id] = []
        draft.ROOM_STATE_VERSION[self.room_id] = 0
        draft.clear_room_caches(self.room_id)

    def tearDown(self):
        draft.DRAFT_PICKS_BY_ROOM.pop(self.room_id, None)
        draft.ROOM_STATE_VERSION.pop(self.room_id, None)
        draft.clear_room_caches(self.room_id)

    def test_position_is_ignored_and_first_open_slot_is_used(self):
        response = self.client.post(
            "/api/draft/picks",
            params={"roomId": self.room_id, "rosterPlayers": 12},
            json={
                "playerId": "12",  # Corbin Burnes (SP)
                "draftedByTeamId": "team-0",
                "slotPos": "C",  # intentionally mismatched
                "bid": 21,
                "type": "mine",
            },
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["slotIndex"], 0)
        self.assertEqual(item["slotPos"], "SP")

    def test_conflict_when_team_roster_is_full(self):
        for player_id in [str(i) for i in range(1, 13)]:
            response = self.client.post(
                "/api/draft/picks",
                params={"roomId": self.room_id, "rosterPlayers": 12},
                json={
                    "playerId": player_id,
                    "draftedByTeamId": "team-0",
                    "slotPos": "C",
                    "bid": 1,
                    "type": "mine",
                },
            )
            self.assertEqual(response.status_code, 200)

        overflow = self.client.post(
            "/api/draft/picks",
            params={"roomId": self.room_id, "rosterPlayers": 12},
            json={
                "playerId": "13",
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

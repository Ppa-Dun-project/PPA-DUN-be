# Unit test for normalized_config
# Basically tests clamping feature works properly.

# Why this function: it runs on every session CRUD call, has multiple branches
# (clamping ranges, name fallbacks, opponent count truncation), and is a pure
# function with no DB / network dependency — ideal for a fast unit test.
import time

import pytest

# a function for normalizing draft configuration
from pages.draft import normalized_config


# ── correctness ──────────────────────────────────────────────────────────────

class TestClamping:
    """Numeric inputs that fall outside allowed ranges must be clamped."""

    def test_budget_below_min_clamped_to_50(self):
        # Budget under 50 must be raised to the 50 floor.
        config, _ = normalized_config(
            league_type="keeper", budget=10, roster_players=20,
            my_team_name="Me", opp_team_names=[], opponents_count=5,
        )
        assert config.budget == 50

    def test_budget_above_max_clamped_to_600(self):
        # Budget over 600 must be capped at the 600 ceiling.
        config, _ = normalized_config(
            league_type="keeper", budget=9999, roster_players=20,
            my_team_name="Me", opp_team_names=[], opponents_count=5,
        )
        assert config.budget == 600

    def test_roster_below_min_clamped_to_12(self):
        # Roster size under 12 must be raised to the 12 floor.
        config, _ = normalized_config(
            league_type="keeper", budget=260, roster_players=5,
            my_team_name="Me", opp_team_names=[], opponents_count=5,
        )
        assert config.rosterPlayers == 12

    def test_roster_above_max_clamped_to_35(self):
        # Roster size over 35 must be capped at the 35 ceiling.
        config, _ = normalized_config(
            league_type="keeper", budget=260, roster_players=100,
            my_team_name="Me", opp_team_names=[], opponents_count=5,
        )
        assert config.rosterPlayers == 35

    def test_opponents_above_max_clamped_to_12(self):
        # Opponent count over 12 must be capped and the team list truncated accordingly.
        config, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Me", opp_team_names=[], opponents_count=50,
        )
        assert config.opponentsCount == 12
        assert len(teams) == 13  # 1 (me) + 12 opponents

    def test_negative_opponents_clamped_to_0(self):
        # Negative opponent count must clamp to 0, leaving only my team.
        config, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Me", opp_team_names=[], opponents_count=-3,
        )
        assert config.opponentsCount == 0
        assert len(teams) == 1
        assert teams[0].isMine is True


class TestTeamBuilding:
    """build_draft_teams (called via normalized_config) must produce stable IDs
    and correct isMine flags."""

    def test_team_ids_are_zero_indexed_and_my_team_is_team_0(self):
        # team-0 is always my team; opponents get sequential team-1, team-2, ... IDs.
        _, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Aces", opp_team_names=["Bears", "Cubs"], opponents_count=2,
        )
        assert teams[0].id == "team-0"
        assert teams[0].isMine is True
        assert teams[1].id == "team-1"
        assert teams[1].isMine is False
        assert teams[2].id == "team-2"

    def test_missing_opponent_names_filled_with_default(self):
        # Fewer names than opponents → unnamed slots get "Opponent N" auto-fill.
        _, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Me", opp_team_names=["Foo"], opponents_count=3,
        )
        assert teams[1].name == "Foo"
        assert teams[2].name == "Opponent 2"
        assert teams[3].name == "Opponent 3"

    def test_empty_opponent_name_falls_back_to_default(self):
        # An empty-string entry must be replaced with the "Opponent N" default.
        _, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Me", opp_team_names=["", "Cubs"], opponents_count=2,
        )
        assert teams[1].name == "Opponent 1"
        assert teams[2].name == "Cubs"

    def test_opp_names_truncated_to_opponents_count(self):
        # Extra opponent names beyond opponents_count must be dropped from both teams and config.
        config, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Me",
            opp_team_names=["A", "B", "C", "D", "E"],
            opponents_count=2,
        )
        assert len(teams) == 3
        assert config.oppTeamNames == ["A", "B"]

    def test_my_team_name_whitespace_stripped(self):
        # Leading/trailing whitespace in my team name must be stripped before storage.
        config, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="  My Squad  ", opp_team_names=[], opponents_count=0,
        )
        assert teams[0].name == "My Squad"
        assert config.myTeamName == "My Squad"

    def test_empty_my_team_name_falls_back_to_default(self):
        # Whitespace-only my team name must fall back to the "My Team" default.
        config, teams = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="   ", opp_team_names=[], opponents_count=0,
        )
        assert teams[0].name == "My Team"
        assert config.myTeamName == "My Team"


class TestConfigOutput:
    def test_config_round_trips_all_fields(self):
        # In-range inputs must pass through unchanged into the returned DraftConfig.
        config, _ = normalized_config(
            league_type="keeper",
            budget=260,
            roster_players=23,
            my_team_name="Aces",
            opp_team_names=["B", "C"],
            opponents_count=2,
            target_season=2026,
        )
        assert config.leagueType == "keeper"
        assert config.budget == 260
        assert config.rosterPlayers == 23
        assert config.myTeamName == "Aces"
        assert config.opponentsCount == 2
        assert config.oppTeamNames == ["B", "C"]
        assert config.targetSeason == 2026

    def test_target_season_defaults_to_none(self):
        # When target_season is omitted, the config field must be None (legacy session compat).
        config, _ = normalized_config(
            league_type="keeper", budget=260, roster_players=20,
            my_team_name="Me", opp_team_names=[], opponents_count=0,
        )
        assert config.targetSeason is None


# ── performance ──────────────────────────────────────────────────────────────

class TestPerformance:
    """normalized_config is called on every session CRUD endpoint. Since the
    PPA architecture moved from batch caching to a per-pick real-time API call,
    the BE handles many sequential requests during a draft — config building
    must stay well under 1ms per call so it never dominates request latency."""

    def test_normalized_config_under_1ms_per_call_average(self):
        # Average call must stay under 1ms across 1000 iterations so config building never dominates latency.
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            normalized_config(
                league_type="keeper",
                budget=260,
                roster_players=23,
                my_team_name="Aces",
                opp_team_names=[f"Team {i}" for i in range(12)],
                opponents_count=12,
            )
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000
        # Generous bound — locally this runs in ~0.05 ms; assert < 1 ms.
        assert avg_ms < 1.0, f"normalized_config avg {avg_ms:.3f} ms exceeds 1 ms budget"

    def test_max_opponents_completes_under_5ms(self):
        # Worst-case single call (max opponents + full name list) must finish well under request budget.
        start = time.perf_counter()
        config, teams = normalized_config(
            league_type="keeper",
            budget=600,
            roster_players=35,
            my_team_name="Me",
            opp_team_names=[f"Opp {i}" for i in range(12)],
            opponents_count=12,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5.0
        assert len(teams) == 13
        assert config.opponentsCount == 12

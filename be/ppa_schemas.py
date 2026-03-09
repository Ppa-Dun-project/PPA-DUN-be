from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


BATTER_POSITIONS = {"C", "1B", "2B", "3B", "SS", "OF", "DH"}
PITCHER_POSITIONS = {"SP", "RP"}
OUTFIELD_POSITION_MAP = {"LF": "OF", "RF": "OF", "CF": "OF"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LeagueContextIn(StrictModel):
    leagueSize: int = Field(ge=1)
    rosterSize: int = Field(ge=1)
    totalBudget: int = Field(ge=1)


class DraftContextIn(StrictModel):
    myRemainingBudget: int = Field(ge=0)
    myRemainingRosterSpots: int = Field(gt=0)
    myPositionsFilled: list[str]
    draftedPlayersCount: int = Field(ge=0)

    @field_validator("myPositionsFilled")
    @classmethod
    def normalize_positions(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in value:
            pos = str(raw).strip().upper()
            if not pos:
                raise ValueError("myPositionsFilled contains an empty position")
            normalized.append(OUTFIELD_POSITION_MAP.get(pos, pos))
        return normalized


class BatterStatsIn(StrictModel):
    AB: int = Field(ge=0)
    R: int = Field(ge=0)
    HR: int = Field(ge=0)
    RBI: int = Field(ge=0)
    SB: int = Field(ge=0)
    CS: int = Field(ge=0)
    AVG: float = Field(ge=0.0)


class PitcherStatsIn(StrictModel):
    IP: float = Field(ge=0.0)
    W: int = Field(ge=0)
    SV: int = Field(ge=0)
    K: int = Field(ge=0)
    ERA: float = Field(ge=0.0)
    WHIP: float = Field(ge=0.0)


def normalize_player_position(player_type: str, raw_position: str) -> str:
    position = raw_position.strip().upper()
    if player_type == "batter":
        mapped = OUTFIELD_POSITION_MAP.get(position, position)
        if mapped not in BATTER_POSITIONS:
            raise ValueError(f"Unsupported batter position: {raw_position}")
        return mapped

    if player_type == "pitcher":
        mapped = "SP" if position == "P" else position
        if mapped not in PITCHER_POSITIONS:
            raise ValueError(f"Unsupported pitcher position: {raw_position}")
        return mapped

    raise ValueError(f"Unsupported playerType: {player_type}")


class BatterValueRequestIn(StrictModel):
    playerName: str = Field(min_length=1)
    playerType: Literal["batter"]
    position: str
    stats: BatterStatsIn
    leagueContext: LeagueContextIn

    @field_validator("position")
    @classmethod
    def validate_position(cls, value: str) -> str:
        return normalize_player_position("batter", value)


class PitcherValueRequestIn(StrictModel):
    playerName: str = Field(min_length=1)
    playerType: Literal["pitcher"]
    position: str
    stats: PitcherStatsIn
    leagueContext: LeagueContextIn

    @field_validator("position")
    @classmethod
    def validate_position(cls, value: str) -> str:
        return normalize_player_position("pitcher", value)


class BatterBidRequestIn(BatterValueRequestIn):
    draftContext: DraftContextIn


class PitcherBidRequestIn(PitcherValueRequestIn):
    draftContext: DraftContextIn


ValueRequestIn = Annotated[
    Union[BatterValueRequestIn, PitcherValueRequestIn],
    Field(discriminator="playerType"),
]

BidRequestIn = Annotated[
    Union[BatterBidRequestIn, PitcherBidRequestIn],
    Field(discriminator="playerType"),
]


class HealthResponseOut(StrictModel):
    status: str


class ValueBreakdownOut(StrictModel):
    statScore: float
    positionBonus: float
    riskPenalty: float


class PlayerValueResponseOut(StrictModel):
    playerName: str
    playerType: Literal["batter", "pitcher"]
    playerValue: float
    valueBreakdown: ValueBreakdownOut


class BidBreakdownOut(StrictModel):
    basePrice: float
    scarcityAdjustment: float
    draftAdjustment: float
    maxSpendable: int


class PlayerBidResponseOut(StrictModel):
    playerName: str
    playerType: Literal["batter", "pitcher"]
    playerValue: float
    recommendedBid: int
    bidBreakdown: BidBreakdownOut


def _build_league_context_payload(league_context: LeagueContextIn) -> dict[str, int]:
    return {
        "league_size": league_context.leagueSize,
        "roster_size": league_context.rosterSize,
        "total_budget": league_context.totalBudget,
    }


def _build_draft_context_payload(draft_context: DraftContextIn) -> dict[str, Any]:
    return {
        "my_remaining_budget": draft_context.myRemainingBudget,
        "my_remaining_roster_spots": draft_context.myRemainingRosterSpots,
        "my_positions_filled": draft_context.myPositionsFilled,
        "drafted_players_count": draft_context.draftedPlayersCount,
    }


def build_value_payload(payload: ValueRequestIn) -> dict[str, Any]:
    return {
        "player_name": payload.playerName,
        "player_type": payload.playerType,
        "position": payload.position,
        "stats": payload.stats.model_dump(),
        "league_context": _build_league_context_payload(payload.leagueContext),
    }


def build_bid_payload(payload: BidRequestIn) -> dict[str, Any]:
    return {
        "player_name": payload.playerName,
        "player_type": payload.playerType,
        "position": payload.position,
        "stats": payload.stats.model_dump(),
        "league_context": _build_league_context_payload(payload.leagueContext),
        "draft_context": _build_draft_context_payload(payload.draftContext),
    }


def map_health_response(raw: dict[str, Any]) -> HealthResponseOut:
    return HealthResponseOut(status=str(raw["status"]))


def map_value_response(raw: dict[str, Any]) -> PlayerValueResponseOut:
    breakdown = raw["value_breakdown"]
    return PlayerValueResponseOut(
        playerName=str(raw["player_name"]),
        playerType=str(raw["player_type"]),
        playerValue=float(raw["player_value"]),
        valueBreakdown=ValueBreakdownOut(
            statScore=float(breakdown["stat_score"]),
            positionBonus=float(breakdown["position_bonus"]),
            riskPenalty=float(breakdown["risk_penalty"]),
        ),
    )


def map_bid_response(raw: dict[str, Any]) -> PlayerBidResponseOut:
    breakdown = raw["bid_breakdown"]
    return PlayerBidResponseOut(
        playerName=str(raw["player_name"]),
        playerType=str(raw["player_type"]),
        playerValue=float(raw["player_value"]),
        recommendedBid=int(raw["recommended_bid"]),
        bidBreakdown=BidBreakdownOut(
            basePrice=float(breakdown["base_price"]),
            scarcityAdjustment=float(breakdown["scarcity_adjustment"]),
            draftAdjustment=float(breakdown["draft_adjustment"]),
            maxSpendable=int(breakdown["max_spendable"]),
        ),
    )

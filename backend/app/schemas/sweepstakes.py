from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class SweepstakesResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    prize_description: str
    status: str
    starts_at: datetime
    ends_at: datetime
    draw_at: datetime | None
    total_entries_count: int
    winner_count: int
    # Apple compliance fields shown in UI
    no_purchase_necessary: bool
    sponsor_name: str
    apple_not_sponsor: bool

    model_config = {"from_attributes": True}


class SweepstakesWithOddsResponse(SweepstakesResponse):
    """
    Extended response that includes the requesting user's personal odds.
    Returned on GET /sweepstakes/{id} (authenticated).
    """
    user_entries: int           # coins this user has entered
    estimated_odds: float | None  # user_entries / total_entries_count (None if 0 total)


class EnterSweepstakesRequest(BaseModel):
    sweepstakes_id: UUID
    coins_to_spend: int         # must be <= user's current coin_balance


class EnterSweepstakesResponse(BaseModel):
    entry_id: UUID
    coins_entered: int
    new_coin_balance: int
    user_total_entries: int
    total_pool_entries: int
    estimated_odds: float


class WinnerResponse(BaseModel):
    id: UUID
    sweepstakes_id: UUID
    prize_description: str
    claim_status: str
    notified_at: datetime | None
    claim_deadline: datetime | None

    model_config = {"from_attributes": True}

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class AdminReviewQueueItem(BaseModel):
    review_id: UUID
    verification_id: UUID
    user_id: UUID
    goal_type_name: str
    goal_local_date: str        # ISO date string in goal's creation timezone
    queued_at: datetime
    sla_deadline: datetime
    priority: int
    photo_urls: list[str]       # pre-signed CloudFront URLs for the reviewer

    model_config = {"from_attributes": True}


class AdminReviewDecisionRequest(BaseModel):
    decision: str               # 'approved' | 'rejected'
    rejection_reason: str | None = None
    reviewer_notes: str | None = None


class AdminReviewDecisionResponse(BaseModel):
    review_id: UUID
    verification_id: UUID
    decision: str
    coins_awarded: int          # 0 if rejected


class TriggerDrawRequest(BaseModel):
    sweepstakes_id: UUID


class TriggerDrawResponse(BaseModel):
    draw_id: UUID
    sweepstakes_id: UUID
    total_entries: int
    total_participants: int
    winners: list[dict]

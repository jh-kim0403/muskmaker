from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel


class RequestUploadUrlRequest(BaseModel):
    """
    Client asks for a pre-signed S3 upload URL before sending a photo.
    Returns a URL the client uploads directly to S3 (photo never touches backend).
    """
    goal_id: UUID
    photo_index: int        # 0 or 1
    mime_type: str = "image/jpeg"


class RequestUploadUrlResponse(BaseModel):
    upload_url: str         # pre-signed S3 PUT URL (expires in 5 minutes)
    s3_key: str             # key to reference this photo in SubmitVerificationRequest
    expires_at: datetime


class SubmitVerificationRequest(BaseModel):
    """
    Sent after all photos have been uploaded to S3.
    The backend then:
      1. Validates all s3_keys exist in S3
      2. Extracts EXIF server-side
      3. Runs anti-cheat checks
      4. Routes to free (manual review) or premium (AI) path
    """
    goal_id: UUID
    verification_path: str      # 'free_manual' | 'premium_ai_standard' | 'premium_ai_location'
    photo_s3_keys: list[str]    # ordered: index 0 first, then index 1

    # Premium location path only. Ignored (and rejected) on all other paths.
    location_lat: Decimal | None = None
    location_lng: Decimal | None = None
    location_accuracy_meters: Decimal | None = None
    location_captured_at: datetime | None = None


class VerificationPhotoResponse(BaseModel):
    id: UUID
    photo_index: int
    photo_url: str          # pre-signed CloudFront URL (time-limited)
    exif_captured_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationResponse(BaseModel):
    id: UUID
    goal_id: UUID
    status: str
    verification_path: str
    submitted_at: datetime
    coins_awarded: int
    coins_awarded_at: datetime | None
    photos: list[VerificationPhotoResponse]
    # Only populated after review
    rejection_reason: str | None
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}

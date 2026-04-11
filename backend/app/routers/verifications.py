from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.verification import (
    RequestUploadUrlRequest,
    RequestUploadUrlResponse,
    SubmitVerificationRequest,
    VerificationResponse,
)
from app.services.storage_service import StorageService
from app.services.verification_service import VerificationService

router = APIRouter(tags=["verifications"])


@router.post("/upload-url", response_model=RequestUploadUrlResponse)
async def request_upload_url(
    body: RequestUploadUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1 of the verification flow.
    Returns a pre-signed S3 PUT URL. The client uploads the photo directly to S3.
    The photo never touches the backend server.

    Call this once per photo (photo_index 0, then 1 for 2-photo paths).
    """
    result = await VerificationService.request_upload_url(
        db=db,
        user=current_user,
        goal_id=body.goal_id,
        photo_index=body.photo_index,
        mime_type=body.mime_type,
    )
    return result


@router.post("/submit", response_model=VerificationResponse, status_code=201)
async def submit_verification(
    body: SubmitVerificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2 of the verification flow.
    Called after all photos have been uploaded to S3.

    The backend will:
      - Validate same-day eligibility using the user's stored timezone
      - Validate path authorization (free vs premium)
      - Extract EXIF server-side
      - Run anti-cheat checks
      - Route to manual review (free) or AI verification (premium)
      - Award coins immediately on premium AI pass
    """
    verification = await VerificationService.submit_verification(
        db=db,
        user=current_user,
        goal_id=body.goal_id,
        verification_path=body.verification_path,
        photo_s3_keys=body.photo_s3_keys,
        location_lat=body.location_lat,
        location_lng=body.location_lng,
        location_accuracy_meters=body.location_accuracy_meters,
        location_captured_at=body.location_captured_at,
    )

    # Build photo response with pre-signed URLs
    response = VerificationResponse(
        id=verification.id,
        goal_id=verification.goal_id,
        status=verification.status,
        verification_path=verification.verification_path,
        submitted_at=verification.submitted_at,
        coins_awarded=verification.coins_awarded,
        coins_awarded_at=verification.coins_awarded_at,
        rejection_reason=verification.rejection_reason,
        reviewed_at=verification.reviewed_at,
        photos=[
            {
                "id": p.id,
                "photo_index": p.photo_index,
                "photo_url": StorageService.get_photo_url(p.s3_key),
                "exif_captured_at": p.exif_captured_at,
                "created_at": p.created_at,
            }
            for p in verification.photos
        ],
    )
    return response


@router.get("/{verification_id}", response_model=VerificationResponse)
async def get_verification(
    verification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll verification status (used by free users waiting for manual review)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.verification import Verification
    from fastapi import HTTPException

    result = await db.execute(
        select(Verification)
        .options(selectinload(Verification.photos))
        .where(
            Verification.id == verification_id,
            Verification.user_id == current_user.id,
        )
    )
    v = result.scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Verification not found")

    return VerificationResponse(
        id=v.id,
        goal_id=v.goal_id,
        status=v.status,
        verification_path=v.verification_path,
        submitted_at=v.submitted_at,
        coins_awarded=v.coins_awarded,
        coins_awarded_at=v.coins_awarded_at,
        rejection_reason=v.rejection_reason,
        reviewed_at=v.reviewed_at,
        photos=[
            {
                "id": p.id,
                "photo_index": p.photo_index,
                "photo_url": StorageService.get_photo_url(p.s3_key),
                "exif_captured_at": p.exif_captured_at,
                "created_at": p.created_at,
            }
            for p in v.photos
        ],
    )

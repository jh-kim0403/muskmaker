"""
StorageService — S3 pre-signed URL generation and EXIF extraction.

Upload flow:
  1. Client calls POST /verifications/upload-url  →  gets pre-signed PUT URL
  2. Client uploads photo directly to S3 (never touches backend)
  3. Client calls POST /verifications/submit with s3_key references
  4. Backend calls extract_exif() server-side to get trusted EXIF data

Photos are NEVER served with their raw S3 key — always use get_photo_url()
to generate a time-limited pre-signed URL.
"""
import io
import logging
import uuid
from datetime import datetime, timezone, timedelta

import boto3
import piexif
import pytz
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

s3_client = boto3.client(
    "s3",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
)


class StorageService:

    @staticmethod
    def generate_photo_s3_key(user_id: str, goal_id: str, photo_index: int) -> str:
        """
        Deterministic S3 key for a verification photo.
        Format: photos/{user_id}/{goal_id}/{index}_{uuid}.jpg
        The UUID suffix prevents key collisions on resubmissions.
        """
        return f"photos/{user_id}/{goal_id}/{photo_index}_{uuid.uuid4()}.jpg"

    @staticmethod
    def generate_upload_url(s3_key: str, mime_type: str = "image/jpeg") -> tuple[str, datetime]:
        """
        Generate a pre-signed S3 PUT URL. The client uploads directly to this URL.
        Returns (upload_url, expires_at).
        """
        expires_in = settings.s3_upload_url_expiry  # seconds
        url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket_photos,
                "Key": s3_key,
                "ContentType": mime_type,
                # Enforce server-side encryption on every upload
                "ServerSideEncryption": "AES256",
            },
            ExpiresIn=expires_in,
        )
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return url, expires_at

    @staticmethod
    def get_photo_url(s3_key: str) -> str:
        """
        Generate a time-limited pre-signed GET URL for photo viewing.
        Used for both the user-facing photo preview and admin review panel.
        """
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_photos, "Key": s3_key},
            ExpiresIn=settings.s3_download_url_expiry,
        )
        return url

    @staticmethod
    def verify_s3_key_exists(s3_key: str) -> bool:
        """Check that a photo was actually uploaded before accepting a verification."""
        try:
            s3_client.head_object(Bucket=settings.s3_bucket_photos, Key=s3_key)
            return True
        except s3_client.exceptions.ClientError:
            return False

    @staticmethod
    def extract_exif(s3_key: str, user_timezone: str = "UTC") -> dict:
        """
        Download the photo from S3 and extract EXIF metadata server-side.
        Returns a dict with keys:
          captured_at, gps_lat, gps_lng, gps_alt_m,
          device_make, device_model, file_size_bytes, width_px, height_px

        NEVER accept EXIF data from the client — always re-extract here.
        """
        response = s3_client.get_object(Bucket=settings.s3_bucket_photos, Key=s3_key)
        raw_bytes = response["Body"].read()

        result = {
            "captured_at": None,
            "gps_lat": None,
            "gps_lng": None,
            "gps_alt_m": None,
            "device_make": None,
            "device_model": None,
            "file_size_bytes": len(raw_bytes),
            "width_px": None,
            "height_px": None,
        }

        try:
            img = Image.open(io.BytesIO(raw_bytes))
            result["width_px"] = img.width
            result["height_px"] = img.height

            exif_bytes = img.info.get("exif")
            if not exif_bytes:
                logger.warning("No EXIF found in photo s3_key=%s", s3_key)
                return result

            exif_data = piexif.load(exif_bytes)

            # ── DateTime ────────────────────────────────────────────────────
            dt_original = (
                exif_data.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                or exif_data.get("0th", {}).get(piexif.ImageIFD.DateTime)
            )
            if dt_original:
                try:
                    dt_str = dt_original.decode("utf-8")
                    naive_dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                    # EXIF DateTimeOriginal is naive local time — localize using the
                    # user's stored timezone before converting to UTC for comparison.
                    tz = pytz.timezone(user_timezone)
                    result["captured_at"] = tz.localize(naive_dt).astimezone(timezone.utc)
                except (ValueError, UnicodeDecodeError):
                    logger.warning("Could not parse EXIF DateTime from s3_key=%s", s3_key)

            # ── Device make / model ──────────────────────────────────────────
            make = exif_data.get("0th", {}).get(piexif.ImageIFD.Make)
            model = exif_data.get("0th", {}).get(piexif.ImageIFD.Model)
            result["device_make"] = make.decode("utf-8", errors="replace").strip("\x00") if make else None
            result["device_model"] = model.decode("utf-8", errors="replace").strip("\x00") if model else None

            # ── GPS ──────────────────────────────────────────────────────────
            gps = exif_data.get("GPS", {})
            if gps:
                lat = StorageService._gps_to_decimal(
                    gps.get(piexif.GPSIFD.GPSLatitude),
                    gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N"),
                )
                lng = StorageService._gps_to_decimal(
                    gps.get(piexif.GPSIFD.GPSLongitude),
                    gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E"),
                )
                result["gps_lat"] = lat
                result["gps_lng"] = lng

                alt_raw = gps.get(piexif.GPSIFD.GPSAltitude)
                if alt_raw:
                    result["gps_alt_m"] = round(alt_raw[0] / alt_raw[1], 2)

        except Exception as exc:
            logger.exception("EXIF extraction failed for s3_key=%s: %s", s3_key, exc)

        return result

    @staticmethod
    def _gps_to_decimal(
        dms: tuple | None, ref: bytes
    ) -> float | None:
        """Convert GPS DMS rational tuple to signed decimal degrees."""
        if not dms or len(dms) < 3:
            return None
        try:
            degrees = dms[0][0] / dms[0][1]
            minutes = dms[1][0] / dms[1][1] / 60
            seconds = dms[2][0] / dms[2][1] / 3600
            decimal = degrees + minutes + seconds
            if ref in (b"S", b"W"):
                decimal = -decimal
            return round(decimal, 8)
        except (ZeroDivisionError, IndexError, TypeError):
            return None

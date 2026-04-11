"""Thin router — notification preferences are managed via /users/me/notification-preferences."""
from fastapi import APIRouter

router = APIRouter(tags=["notifications"])

# Notification preference endpoints live in users.py for REST resource consistency.
# This router is reserved for future notification-specific endpoints
# (e.g., GET /notifications/history, POST /notifications/test).

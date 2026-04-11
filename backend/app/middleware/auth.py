"""
Firebase JWT verification middleware.

Verifies the Authorization: Bearer <token> header on every request EXCEPT
public routes (health check, RevenueCat webhooks which use their own HMAC secret).

On success: attaches decoded token dict to request.state.firebase_user.
On failure: returns 401 immediately.
"""
import logging
from typing import Awaitable, Callable

import firebase_admin.auth as firebase_auth
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Routes that do NOT require a Firebase JWT
PUBLIC_PATHS = {
    "/health",
    "/api/v1/webhooks/revenuecat",   # uses its own HMAC secret
    "/api/v1/webhooks/apple",        # Apple server notifications
    "/docs",
    "/redoc",
    "/openapi.json",
}


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or malformed Authorization header"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            decoded = firebase_auth.verify_id_token(token, check_revoked=True)
            request.state.firebase_user = decoded
        except firebase_auth.RevokedIdTokenError:
            return JSONResponse(status_code=401, content={"detail": "Token has been revoked"})
        except firebase_auth.ExpiredIdTokenError:
            return JSONResponse(status_code=401, content={"detail": "Token has expired"})
        except firebase_auth.InvalidIdTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        except Exception as exc:
            logger.exception("Unexpected error during Firebase token verification: %s", exc)
            return JSONResponse(status_code=401, content={"detail": "Authentication failed"})

        return await call_next(request)

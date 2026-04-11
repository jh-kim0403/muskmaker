"""
MuskMaker FastAPI application factory.

Startup order:
  1. Firebase Admin SDK initialized
  2. APScheduler background workers started
  3. Routers mounted
  4. Middleware registered (order matters — outermost runs first on request)
"""
import logging
from contextlib import asynccontextmanager

import firebase_admin
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.middleware.auth import FirebaseAuthMiddleware
from app.middleware.rate_limit import limiter
from app.routers import admin, goals, notifications, sweepstakes, users, verifications, webhooks
from app.workers.goal_expiry_worker import expire_stale_goals
from app.workers.notification_worker import send_goal_reminders

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Background scheduler ───────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    # Firebase Admin SDK (used for JWT verification in every request)
    if not firebase_admin._apps:
        cred = firebase_admin.credentials.Certificate(settings.firebase_service_account_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized")

    # Background workers
    # Expire stale goals every 15 minutes (goals whose local day has ended)
    scheduler.add_job(expire_stale_goals, "interval", minutes=15, id="goal_expiry")
    # Send goal-expiry reminder pushes every 5 minutes
    scheduler.add_job(send_goal_reminders, "interval", minutes=5, id="goal_reminders")
    scheduler.start()
    logger.info("Background scheduler started")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Background scheduler stopped")


# ── App factory ────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        # Disable auto-generated docs in production
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── Rate limiter (slowapi) ─────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ───────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Security headers ───────────────────────────────────────────────────────
    app.add_middleware(FirebaseAuthMiddleware)

    # ── Routers ────────────────────────────────────────────────────────────────
    API_PREFIX = "/api/v1"

    app.include_router(users.router,         prefix=f"{API_PREFIX}/users")
    app.include_router(goals.router,         prefix=f"{API_PREFIX}/goals")
    app.include_router(verifications.router, prefix=f"{API_PREFIX}/verifications")
    app.include_router(sweepstakes.router,   prefix=f"{API_PREFIX}/sweepstakes")
    app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications")
    app.include_router(webhooks.router,      prefix=f"{API_PREFIX}/webhooks")
    app.include_router(admin.router,         prefix=f"{API_PREFIX}/admin")

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()

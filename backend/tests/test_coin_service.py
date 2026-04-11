"""
Tests for CoinService — fairness and atomicity of coin operations.

Key invariants:
  1. coin_balance can never go negative
  2. Coins are earned from goal_type.coin_reward — never from subscription tier
  3. Ledger is append-only
  4. Entry cannot exist without a corresponding ledger debit
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.coin_service import CoinService
from app.constants import CoinTxType


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid4()
    user.coin_balance = 10
    return user


@pytest.fixture
def mock_verification():
    v = MagicMock()
    v.id = uuid4()
    v.goal_id = uuid4()
    v.coins_awarded = 0
    return v


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestAwardCoins:
    @pytest.mark.asyncio
    async def test_credits_correct_amount(self, mock_db, mock_user, mock_verification):
        await CoinService.award_coins_for_verification(
            db=mock_db, user=mock_user, verification=mock_verification, coin_amount=5
        )
        assert mock_user.coin_balance == 15  # 10 + 5

    @pytest.mark.asyncio
    async def test_stamps_verification(self, mock_db, mock_user, mock_verification):
        await CoinService.award_coins_for_verification(
            db=mock_db, user=mock_user, verification=mock_verification, coin_amount=3
        )
        assert mock_verification.coins_awarded == 3
        assert mock_verification.coins_awarded_at is not None

    @pytest.mark.asyncio
    async def test_rejects_zero_coins(self, mock_db, mock_user, mock_verification):
        with pytest.raises(ValueError, match="positive"):
            await CoinService.award_coins_for_verification(
                db=mock_db, user=mock_user, verification=mock_verification, coin_amount=0
            )

    @pytest.mark.asyncio
    async def test_rejects_double_award(self, mock_db, mock_user, mock_verification):
        mock_verification.coins_awarded = 5  # already awarded
        with pytest.raises(ValueError, match="already awarded"):
            await CoinService.award_coins_for_verification(
                db=mock_db, user=mock_user, verification=mock_verification, coin_amount=5
            )

    @pytest.mark.asyncio
    async def test_coin_reward_independent_of_tier(self, mock_db, mock_verification):
        """
        CRITICAL FAIRNESS TEST: free and premium users with the same goal type
        must receive identical coin awards.
        """
        free_user = MagicMock()
        free_user.id = uuid4()
        free_user.coin_balance = 0
        free_user.subscription_tier = "free"

        premium_user = MagicMock()
        premium_user.id = uuid4()
        premium_user.coin_balance = 0
        premium_user.subscription_tier = "premium"

        free_verification = MagicMock()
        free_verification.id = uuid4()
        free_verification.goal_id = uuid4()
        free_verification.coins_awarded = 0

        premium_verification = MagicMock()
        premium_verification.id = uuid4()
        premium_verification.goal_id = uuid4()
        premium_verification.coins_awarded = 0

        # Same coin_reward (from goal_type) — same result regardless of tier
        reward = 7
        await CoinService.award_coins_for_verification(mock_db, free_user, free_verification, reward)
        await CoinService.award_coins_for_verification(mock_db, premium_user, premium_verification, reward)

        assert free_user.coin_balance == premium_user.coin_balance == reward


class TestSpendCoins:
    @pytest.mark.asyncio
    async def test_rejects_insufficient_balance(self, mock_db, mock_user):
        mock_user.coin_balance = 3
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await CoinService.spend_coins_for_entry(
                db=mock_db, user=mock_user, sweepstakes_id=uuid4(), coins_to_spend=10
            )
        assert exc_info.value.status_code == 422
        assert "Insufficient" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_balance_never_goes_negative(self, mock_db, mock_user):
        mock_user.coin_balance = 5
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            await CoinService.spend_coins_for_entry(
                db=mock_db, user=mock_user, sweepstakes_id=uuid4(), coins_to_spend=6
            )
        # Balance must remain unchanged after failed spend
        assert mock_user.coin_balance == 5

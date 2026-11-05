"""Ответ кабинета передаёт выбранный период автопродления как есть."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.cabinet.routes.subscription_modules.helpers import _subscription_to_response
from app.database.models import Subscription, SubscriptionStatus


def _subscription() -> Subscription:
    now = datetime.now(UTC)
    return Subscription(
        id=1,
        user_id=1,
        status=SubscriptionStatus.ACTIVE.value,
        is_trial=False,
        tariff_id=7,
        start_date=now - timedelta(days=5),
        end_date=now + timedelta(days=10),
        traffic_limit_gb=0,
        traffic_used_gb=0.0,
        device_limit=3,
        connected_squads=[],
        autopay_enabled=False,
        autopay_days_before=3,
    )


def test_response_carries_autopay_period_days():
    subscription = _subscription()
    subscription.autopay_period_days = 60

    response = _subscription_to_response(subscription)

    assert response.autopay_period_days == 60


def test_response_autopay_period_days_defaults_to_none():
    response = _subscription_to_response(_subscription())

    assert response.autopay_period_days is None

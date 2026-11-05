"""Варианты продления передают число устройств, включённых в доплату."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('device_limit', 'expected_extra_devices', 'expected_price_kopeks'),
    [(4, 1, 45000), (3, 0, 30000)],
    ids=['extra-device', 'included-devices'],
)
async def test_renewal_option_includes_extra_devices(
    monkeypatch, device_limit, expected_extra_devices, expected_price_kopeks
) -> None:
    from app.cabinet.routes.subscription_modules.renewal import get_renewal_options

    monkeypatch.setattr(settings, 'SALES_MODE', 'tariffs')
    monkeypatch.setattr(settings, 'MULTI_TARIFF_ENABLED', False)

    async with memory_session(monkeypatch, TABLES) as db:
        now = datetime.now(UTC)
        db.add_all(
            [
                User(id=1, telegram_id=1001, first_name='Даниил', language='ru', status='active', balance_kopeks=50000),
                Tariff(
                    id=1,
                    name='Уверенный стандарт',
                    description='',
                    is_active=True,
                    is_daily=False,
                    period_prices={'30': 30000},
                    traffic_limit_gb=100,
                    device_limit=3,
                    device_price_kopeks=15000,
                    allowed_squads=[],
                    display_order=1,
                ),
                Subscription(
                    id=10,
                    remnawave_short_id='standard1',
                    remnawave_id=9001,
                    user_id=1,
                    status=SubscriptionStatus.ACTIVE.value,
                    is_trial=False,
                    start_date=now - timedelta(days=5),
                    end_date=now + timedelta(days=25),
                    traffic_limit_gb=100,
                    traffic_used_gb=0.0,
                    device_limit=device_limit,
                    tariff_id=1,
                    connected_squads=[],
                ),
            ]
        )
        await db.commit()
        db.expunge_all()
        user = await db.get(User, 1)

        options = await get_renewal_options(user=user, db=db, subscription_id=10)

    assert [option.period_days for option in options] == [30]
    assert options[0].extra_devices == expected_extra_devices
    assert options[0].price_kopeks == expected_price_kopeks

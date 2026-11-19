"""Форк: managed-подписка в открытом grace честно не меняет тариф.

Раньше превью отвечало can_switch=true, а сама смена — 409 «Tariff changes are
unavailable during grace» по-английски. Теперь и превью, и смена отказывают кодом
grace_switch_unavailable (кабинет переводит его в «докупите трафик или дождитесь
сброса»), денег не трогают. Без grace managed-подписка тариф меняет как раньше.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.cabinet.schemas.subscription import TariffPurchaseRequest
from app.database.models import Subscription, Transaction
from tests.database.test_multi_tariff_switch_postgres import route, switch_data


pytestmark = pytest.mark.postgres


async def _managed_limited(db, *, grace_open: bool) -> Subscription:
    source = await db.get(Subscription, 11)
    source.status = 'limited'
    source.traffic_used_gb = 150.03
    source.traffic_accounting_mode = 'managed'
    source.grace_session_open = grace_open
    await db.commit()
    return source


@pytest.mark.parametrize(('action', 'expected_status'), [('preview', 400), ('switch', 409)])
async def test_managed_subscription_in_grace_gets_coded_refusal(
    postgres_database, monkeypatch, action, expected_status
):
    async with switch_data(postgres_database, monkeypatch) as (db, user):
        await _managed_limited(db, grace_open=True)
        await db.refresh(user, ['subscriptions'])
        handler = route.preview_tariff_switch if action == 'preview' else route.switch_tariff

        with pytest.raises(HTTPException) as exc:
            await handler(TariffPurchaseRequest(tariff_id=3, period_days=30), user, db, 11)

        assert exc.value.status_code == expected_status
        assert exc.value.detail['code'] == 'grace_switch_unavailable'
        await db.refresh(user)
        assert user.balance_kopeks == 10000
        assert (await db.scalars(select(Transaction))).all() == []


async def test_managed_subscription_without_grace_still_previews(postgres_database, monkeypatch):
    async with switch_data(postgres_database, monkeypatch) as (db, user):
        await _managed_limited(db, grace_open=False)
        await db.refresh(user, ['subscriptions'])

        result = await route.preview_tariff_switch(TariffPurchaseRequest(tariff_id=3, period_days=30), user, db, 11)

        assert result['can_switch'] is True


async def test_legacy_subscription_ignores_the_grace_flag(postgres_database, monkeypatch):
    async with switch_data(postgres_database, monkeypatch) as (db, user):
        source = await _managed_limited(db, grace_open=True)
        source.traffic_accounting_mode = 'legacy'
        await db.commit()
        await db.refresh(user, ['subscriptions'])

        result = await route.preview_tariff_switch(TariffPurchaseRequest(tariff_id=3, period_days=30), user, db, 11)

        assert result['can_switch'] is True

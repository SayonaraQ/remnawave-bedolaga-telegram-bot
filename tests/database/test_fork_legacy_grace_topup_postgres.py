"""Форк: докупка legacy-подписки в grace по трафику — без перевода в учёт.

Решение владельца 03.11 (RUNBOOK_UPGRADE_BOT520_CABINET182, Б1): докупка — штатный
выход из grace, как в 5.1.1. Legacy-подписку в grace покупаем по-старому: снимок
панели не нужен, перевод в managed сделает воркер после закрытия grace. Апстрим
5.2.1 вместо этого переводит её сразу; его legacy-ожидания пропущены в
test_limited_grace_topup_postgres.py.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.database.crud.user import subtract_user_balance
from app.database.models import Base, Subscription, User
from app.services.traffic_accounting_store import load_account
from app.services.traffic_purchase_service import add_subscription_traffic, prepare_traffic_purchase
from tests.database.test_limited_grace_topup_postgres import GRACE, seed
from tests.fixtures.postgres_db import postgres_sessions


pytestmark = pytest.mark.postgres


@pytest.mark.parametrize('rollback', [False, True])
async def test_legacy_topup_in_traffic_grace_stays_legacy(postgres_database, monkeypatch, rollback):
    async with postgres_sessions(postgres_database, list(Base.metadata.sorted_tables)) as (db, observer):
        sub, user, api = await seed(db, monkeypatch, managed=False)
        end = sub.end_date
        sub, panel = await prepare_traffic_purchase(db, sub, requested_gb=5)
        assert panel is None, 'legacy в grace: снимок панели не читается'
        assert await subtract_user_balance(db, user, 100, 'test traffic', commit=False)
        await add_subscription_traffic(db, sub, 5, panel=panel, commit=False)
        if rollback:
            await db.rollback()
        else:
            await db.commit()
        stored = await observer.get(Subscription, 1)
        await observer.refresh(stored)
        assert stored.end_date == end, 'докупка не продлевает срок'
        assert stored.traffic_limit_gb == (10 if rollback else 15)
        assert (await observer.get(User, 1)).balance_kopeks == (1000 if rollback else 900)
        assert stored.traffic_accounting_mode == 'legacy'
        assert await load_account(observer, 1) is None, 'перевода в учёт нет'
        assert api.updates == [], 'подготовка покупки панель не пишет'
        assert api.user.active_internal_squads == [{'uuid': GRACE}]


@pytest.mark.parametrize('case', ['expired', 'trial', 'blocked'])
async def test_legacy_topup_refuses_ineligible_grace(postgres_database, monkeypatch, case):
    from app.services.traffic_accounting import AccountingConflict

    async with postgres_sessions(postgres_database, list(Base.metadata.sorted_tables)) as (db, observer):
        sub, user, api = await seed(db, monkeypatch, managed=False)
        if case == 'expired':
            sub.end_date = datetime.now(UTC) - timedelta(seconds=1)
        elif case == 'trial':
            sub.is_trial = True
        else:
            user.status = 'blocked'
        await db.commit()
        with pytest.raises(AccountingConflict):
            await prepare_traffic_purchase(db, sub, requested_gb=5)
        await db.rollback()
        assert (await observer.get(User, 1)).balance_kopeks == 1000
        assert (await observer.get(Subscription, 1)).traffic_limit_gb == 10

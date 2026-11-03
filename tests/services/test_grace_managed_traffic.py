"""Grace по трафику поверх управляемого учёта трафика (5.2.0).

Апстрим 5.2.0 запрещает докупку при открытом grace, не выдаёт базу 1-го числа,
пока grace открыт, и пересчитывает расход managed-подписки только вне grace.
Для режима «без белых списков» это значило: оплатить нельзя, а после сброса белые
списки не возвращаются до конца подписки. Здесь — правки форка.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import update

from app.services.traffic_accounting import AccountingConflict, Allowance, TrafficAccount
from tests.services.test_grace_access_notifications import lab  # noqa: F401 — фикстура
from tests.services.test_grace_strip_renewal_guards import _open, _session, db_maker  # noqa: F401 — фикстура
from tests.services.test_traffic_accounting_service import NOW, snapshot


GIB = 1024**3
IDENTITY = '123@2025-11-16T00:00:00+00:00'


# --- учёт: база 1-го числа при открытом grace ---------------------------------


async def _managed_due(db, *, grace_excluded: bool):
    from app.database.models import Subscription
    from app.services.traffic_accounting_store import initialize_account

    state = await initialize_account(
        db,
        1,
        TrafficAccount(IDENTITY, 100, 100, (Allowance('base:nov', 0, NOW, GIB),)),
        strategy='MONTH',
        timezone='UTC',
        anchor=NOW,
        next_refresh_at=NOW,
    )
    state.phase = 'ready'
    state.grace_excluded = grace_excluded
    sub = await db.get(Subscription, 1)
    sub.traffic_accounting_mode = 'managed'
    sub.traffic_limit_gb = 2
    sub.purchased_traffic_gb = 0
    sub.remnawave_id = 123
    await db.commit()
    return sub


async def test_calendar_base_waits_for_grace_unless_grace_asks(monkeypatch):
    from app.services.traffic_accounting_service import lock_accounting_subscription, reconcile_account_locked
    from tests.services.test_traffic_accounting_store import database

    async with database(monkeypatch) as db:
        await _managed_due(db, grace_excluded=True)
        panel = snapshot(used=100, lifetime=100, strategy='NO_RESET')
        sub, _ = await lock_accounting_subscription(db, 1)
        held = await reconcile_account_locked(db, sub, panel, now=NOW)
        assert held.remaining_bytes(NOW) == 0, 'апстрим: при grace база ждёт выхода'
        granted = await reconcile_account_locked(db, sub, panel, now=NOW, refresh_during_grace=True)
        assert granted.remaining_bytes(NOW) == 2 * GIB


async def test_grace_grants_the_due_base_itself(monkeypatch):
    from app.services import grace_access_runtime as rt, traffic_accounting_service as accounting
    from app.services.remnawave_service import remnawave_service
    from app.services.traffic_accounting_store import load_account
    from tests.services.test_traffic_accounting_store import database

    @asynccontextmanager
    async def client():
        yield object()

    async def fresh(*args):
        return snapshot(used=100, lifetime=100, strategy='NO_RESET')

    monkeypatch.setattr(remnawave_service, 'get_api_client', client)
    monkeypatch.setattr(accounting, '_fresh_panel', fresh)
    session = replace(_session(strip=True), subscription_id=1, remnawave_id=123)

    async with database(monkeypatch) as db:
        await _managed_due(db, grace_excluded=True)
        assert await rt._grant_managed_base_if_due(db, session, now=NOW - timedelta(minutes=1)) is False
        assert await rt._grant_managed_base_if_due(db, session, now=NOW) is True
        account, state = await load_account(db, 1)
        assert account.remaining_bytes(NOW) == 2 * GIB
        assert state.next_refresh_at > NOW, 'следующая база — по календарю, не повторно'
        assert state.grace_excluded is True, 'расход за время grace по-прежнему не списывается'
        assert await rt._grant_managed_base_if_due(db, session, now=NOW) is False


async def test_grace_base_grant_survives_a_panel_failure(monkeypatch):
    from app.services import grace_access_runtime as rt, traffic_accounting_service as accounting
    from app.services.remnawave_service import remnawave_service
    from tests.services.test_traffic_accounting_store import database

    @asynccontextmanager
    async def client():
        yield object()

    async def broken(*args):
        raise ConnectionError('panel down')

    monkeypatch.setattr(remnawave_service, 'get_api_client', client)
    monkeypatch.setattr(accounting, '_fresh_panel', broken)
    session = replace(_session(strip=True), subscription_id=1, remnawave_id=123)
    async with database(monkeypatch) as db:
        await _managed_due(db, grace_excluded=True)
        assert await rt._grant_managed_base_if_due(db, session, now=NOW) is False


# --- биллинг grace: расход managed = номинал − остаток -----------------------


async def test_billing_reads_managed_usage_from_the_ledger(monkeypatch):
    from app.database.models import Subscription
    from app.services.grace_access_runtime import SQLAlchemyGraceBillingGateway
    from app.services.traffic_accounting_store import initialize_account
    from tests.services.test_traffic_accounting_store import database

    now = datetime.now(UTC)
    async with database(monkeypatch) as db:
        sub = await db.get(Subscription, 1)
        sub.traffic_limit_gb = 10
        sub.traffic_used_gb = 3.0
        await db.commit()
        legacy = await SQLAlchemyGraceBillingGateway(db).get_subscription(1)
        assert legacy.traffic_managed is False
        assert legacy.used_traffic_bytes == 3 * GIB

        state = await initialize_account(
            db,
            1,
            TrafficAccount(
                IDENTITY,
                0,
                0,
                (
                    Allowance('base:nov', GIB // 2, now + timedelta(days=5)),
                    # Истёкший пакет в остаток не входит.
                    Allowance('purchase:1', GIB, now - timedelta(minutes=1)),
                ),
            ),
            strategy='MONTH',
            timezone='UTC',
            anchor=now,
            next_refresh_at=now + timedelta(days=5),
        )
        state.phase = 'ready'
        sub = await db.get(Subscription, 1)
        sub.traffic_accounting_mode = 'managed'
        await db.commit()
        state.last_base_operation_at = now - timedelta(days=2)
        await db.commit()
        managed = await SQLAlchemyGraceBillingGateway(db).get_subscription(1)
        assert managed.traffic_managed is True
        assert managed.used_traffic_bytes == 10 * GIB - GIB // 2
        assert managed.traffic_period_at == now - timedelta(days=2)


@pytest.mark.parametrize('panel_used_gb', [500, 40])
async def test_managed_usage_is_not_mixed_with_the_panel_counter(panel_used_gb):
    """Панель на NO_RESET: её счётчик с номиналом не сравним — ни вверх, ни вниз."""
    from tests.services.test_grace_limited_strip import MIB, limited_billing, limited_snapshot, started

    panel_used = panel_used_gb * GIB
    result, *_ = await started(
        billing=limited_billing(traffic_managed=True),
        snapshot=limited_snapshot(used_traffic_bytes=panel_used, traffic_limit_bytes=panel_used),
    )
    session = result.session
    assert session.billing_before.used_traffic_bytes == 70 * GIB, 'сброс сравнивается в системе учёта бота'
    assert session.panel_before.used_traffic_bytes == panel_used
    assert session.overlay.traffic_limit_bytes == panel_used + 100 * MIB, 'запас — от настоящего счётчика панели'


async def test_panel_counter_drop_is_not_a_reset_for_managed(db_maker):
    from app.services.grace_access_runtime import _adopt_panel_traffic_reset

    session = _session(strip=True)
    billing = SimpleNamespace(traffic_managed=True, used_traffic_bytes=70 * GIB)

    class Panel:
        async def read_snapshot(self, remnawave_id):
            raise AssertionError('managed не должен читать счётчик панели')

    async with db_maker() as db:
        assert await _adopt_panel_traffic_reset(db, session, billing, panel=Panel()) is False


# --- докупка при открытом grace ------------------------------------------------


async def test_only_an_active_traffic_grace_accepts_a_purchase(db_maker, monkeypatch):
    from app.database.models import GraceAccessSessionModel
    from app.services import grace_access_runtime as rt

    monkeypatch.setattr(rt.settings, 'MULTI_TARIFF_ENABLED', True)
    monkeypatch.setattr(rt.settings, 'SALES_MODE', 'tariffs')
    async with db_maker() as db:
        assert await rt.limited_grace_accepts_traffic_purchase(db, 42) is False
    await _open(db_maker, strip=True)
    async with db_maker() as db:
        assert await rt.limited_grace_accepts_traffic_purchase(db, 42) is True
        await db.execute(update(GraceAccessSessionModel).values(reason='expired'))
        assert await rt.limited_grace_accepts_traffic_purchase(db, 42) is False
        await db.execute(update(GraceAccessSessionModel).values(reason='limited', state='restoring'))
        assert await rt.limited_grace_accepts_traffic_purchase(db, 42) is False


def _purchase_doubles(monkeypatch, *, mode: str, grace_open: bool, accepts: bool):
    order: list[str] = []
    sub = SimpleNamespace(
        id=1,
        user_id=1,
        tariff_id=None,
        tariff=None,
        traffic_limit_gb=10,
        purchased_traffic_gb=0,
        end_date=None,
        status='limited',
        is_trial=False,
        traffic_accounting_mode=mode,
        grace_session_open=True,
    )
    panel = object()

    @asynccontextmanager
    async def client():
        yield object()

    async def migrate(*args, **kwargs):
        order.append('migration')

    async def lock(*args):
        order.append('lease')
        return sub, grace_open

    async def read(*args):
        order.append('snapshot')
        return panel

    async def accepted(db, subscription_id):
        return accepts

    monkeypatch.setattr(
        'app.services.traffic_purchase_service.SubscriptionService', lambda: SimpleNamespace(get_api_client=client)
    )
    monkeypatch.setattr('app.services.traffic_accounting_service.ensure_managed_account', migrate)
    monkeypatch.setattr('app.services.traffic_accounting_service.lock_accounting_subscription', lock)
    monkeypatch.setattr('app.services.traffic_accounting_service._fresh_panel', read)
    monkeypatch.setattr('app.services.grace_access_runtime.limited_grace_accepts_traffic_purchase', accepted)
    return sub, panel, order


async def test_legacy_subscription_in_traffic_grace_buys_the_old_way(monkeypatch):
    from app.services.traffic_purchase_service import prepare_traffic_purchase

    sub, _, order = _purchase_doubles(monkeypatch, mode='legacy', grace_open=True, accepts=True)
    assert await prepare_traffic_purchase(SimpleNamespace(bind=None), sub) == (sub, None)
    assert order == ['lease'], 'без перевода в учёт: он прочитал бы оверлей панели как остаток'


async def test_managed_subscription_in_traffic_grace_buys_into_the_ledger(monkeypatch):
    from app.services.traffic_purchase_service import prepare_traffic_purchase

    sub, panel, order = _purchase_doubles(monkeypatch, mode='managed', grace_open=True, accepts=True)
    assert await prepare_traffic_purchase(SimpleNamespace(bind=None), sub) == (sub, panel)
    assert order == ['migration', 'lease', 'snapshot']


async def test_other_open_grace_still_blocks_a_purchase(monkeypatch):
    from app.services.traffic_purchase_service import prepare_traffic_purchase

    sub, _, _ = _purchase_doubles(monkeypatch, mode='managed', grace_open=True, accepts=False)
    with pytest.raises(AccountingConflict, match='Finish temporary'):
        await prepare_traffic_purchase(SimpleNamespace(bind=None), sub)


async def test_grace_closing_mid_purchase_asks_for_a_retry(monkeypatch):
    from app.services.traffic_purchase_service import prepare_traffic_purchase

    sub, _, _ = _purchase_doubles(monkeypatch, mode='legacy', grace_open=False, accepts=True)
    with pytest.raises(AccountingConflict, match='retry'):
        await prepare_traffic_purchase(SimpleNamespace(bind=None), sub)


# --- уведомление: дата сброса из учёта ------------------------------------------


def test_managed_reset_label_uses_the_ui_timezone(monkeypatch):
    from app.services import grace_access_notifications as notify

    monkeypatch.setattr('app.utils.timezone.get_local_timezone', lambda: ZoneInfo('Europe/Moscow'))
    assert notify.managed_reset_label(datetime(2026, 12, 1, 0, 20, tzinfo=UTC)) == '01.12'
    assert notify.managed_reset_label(datetime(2026, 11, 30, 22, 30, tzinfo=UTC)) == '01.12'


async def test_strip_grant_names_the_ledger_reset_date(lab, monkeypatch):
    from app.database.models import Subscription
    from app.services import grace_access_notifications as notify
    from app.services.traffic_accounting_store import initialize_account
    from tests.services.test_grace_strip_notifications import _seed_strip

    monkeypatch.setattr('app.utils.timezone.get_local_timezone', lambda: ZoneInfo('Europe/Moscow'))
    await _seed_strip(lab.maker, strategy='NO_RESET')
    async with lab.maker() as db:
        await db.execute(update(Subscription).values(traffic_accounting_mode='managed'))
        await initialize_account(
            db,
            10,
            TrafficAccount(IDENTITY, 0, 0, ()),
            strategy='MONTH',
            timezone='UTC',
            anchor=NOW,
            next_refresh_at=datetime(2027, 2, 1, 0, 20, tzinfo=UTC),
        )
        await db.commit()

    await notify.announce_grace_event(lab.bot, 10, 'granted')

    message = lab.user.await_args.kwargs['telegram_message']
    assert 'недоступны до 01.02.' in message, message


def test_managed_incident_key_follows_the_ledger_base_not_the_panel():
    """Прод 03.11, тест-юзер: база 1-го числа закрыла grace, второе исчерпание
    получило тот же ключ (панель на NO_RESET не сбрасывает) — grace не выдавался."""
    from app.services.grace_access_service import GraceReason, build_incident_key
    from tests.services.test_grace_limited_strip import limited_billing

    panel_reset = datetime(2026, 10, 1, 0, 20, tzinfo=UTC)
    november = limited_billing(traffic_managed=True, traffic_period_at=datetime(2026, 11, 3, 20, tzinfo=UTC))
    december = replace(november, traffic_period_at=datetime(2026, 12, 1, 0, 20, tzinfo=UTC))
    key = build_incident_key(november, GraceReason.LIMITED, last_traffic_reset_at=panel_reset)
    assert key != build_incident_key(december, GraceReason.LIMITED, last_traffic_reset_at=panel_reset)
    assert key == build_incident_key(november, GraceReason.LIMITED, last_traffic_reset_at=None)
    legacy = limited_billing()
    assert build_incident_key(legacy, GraceReason.LIMITED, last_traffic_reset_at=panel_reset).endswith(
        panel_reset.isoformat()
    )


@pytest.mark.parametrize(
    ('managed', 'quota_disabled', 'starts'),
    [(True, True, True), (True, False, False), (False, False, False)],
    ids=['managed_quota_cut', 'admin_disabled', 'legacy_disabled'],
)
async def test_managed_quota_cut_is_a_traffic_incident(managed, quota_disabled, starts):
    """Прод 03.11, тест-юзер: продлили истёкшую подписку с нулевым остатком — учёт
    поставил панели DISABLED, grace по трафику счёл это отключением и не выдал режим."""
    from app.services.grace_access_service import GraceStartDecision
    from tests.services.test_grace_limited_strip import WL_SQUAD, limited_billing, limited_snapshot, started

    result, *_ = await started(
        billing=limited_billing(traffic_managed=managed, traffic_quota_disabled=quota_disabled),
        snapshot=limited_snapshot(status='DISABLED'),
    )
    if starts:
        assert result.decision is GraceStartDecision.STARTED
        assert result.session.overlay.status == 'ACTIVE'
        assert WL_SQUAD not in result.session.overlay.squad_uuids
    else:
        assert result.decision is GraceStartDecision.SUPERSEDED

"""Продление днями в режиме «без белых списков» не должно возвращать канон мимо grace.

Прод, 03.11, тест-юзер: продление поставило подписке ``active``; вебхук
user.modified увидел в панели дату оверлея (она короче оплаченной) и поставил
повтор; повтор через ``update_remnawave_user`` записал полный канон — белые
списки вернулись при исчерпанном трафике, панель снова LIMITED, новая сессия.
Каждая запись рождала новый user.modified — круг мог не кончиться.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.models import Base, Subscription, SubscriptionStatus, User
from app.services.grace_access_service import (
    GraceAccessSession,
    GraceBillingState,
    GracePanelOverlay,
    GracePanelSnapshot,
    GraceReason,
    GraceSessionState,
)


GIB = 1024**3
PANEL_ID = 9001
NOW = datetime.now(UTC)
END_AT = NOW + timedelta(days=20)
EU = 'aaaaaaaa-0000-0000-0000-000000000001'
WL = 'bbbbbbbb-0000-0000-0000-000000000003'


def _session(*, strip: bool) -> GraceAccessSession:
    billing = GraceBillingState(
        subscription_id=42,
        remnawave_id=PANEL_ID,
        status='limited',
        end_at=END_AT,
        traffic_limit_bytes=70 * GIB,
        used_traffic_bytes=70 * GIB,
        device_limit=3,
        squad_uuids=(EU, WL),
    )
    return GraceAccessSession(
        id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
        subscription_id=42,
        remnawave_id=PANEL_ID,
        reason=GraceReason.LIMITED,
        incident_key='limited:test',
        state=GraceSessionState.ACTIVE,
        billing_before=billing,
        panel_before=GracePanelSnapshot(
            remnawave_id=PANEL_ID,
            status='LIMITED',
            expire_at=END_AT,
            traffic_limit_bytes=70 * GIB,
            used_traffic_bytes=70 * GIB,
            squad_uuids=(EU, WL),
        ),
        overlay=GracePanelOverlay(
            status='ACTIVE',
            expire_at=END_AT - timedelta(seconds=60),
            traffic_limit_bytes=70 * GIB + 100 * 1024**2,
            squad_uuids=(EU,) if strip else ('grace',),
            strip_squads=strip,
        ),
        started_at=NOW,
        grace_until=END_AT - timedelta(seconds=60),
        updated_at=NOW,
    )


@pytest_asyncio.fixture
async def db_maker(monkeypatch):
    from tests.fixtures.sqlite_memory import ensure_real_aiosqlite

    ensure_real_aiosqlite(monkeypatch)
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=list(Base.metadata.sorted_tables)))
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as db:
        db.add(User(id=1, telegram_id=1001, first_name='U', language='ru', status='active', balance_kopeks=0))
        await db.flush()
        db.add(
            Subscription(
                id=42,
                remnawave_short_id='sub42',
                user_id=1,
                # Продлили днями: бот держит active, трафик исчерпан.
                status='active',
                is_trial=False,
                start_date=NOW - timedelta(days=10),
                end_date=END_AT + timedelta(days=30),
                traffic_limit_gb=70,
                traffic_used_gb=70.0,
                device_limit=3,
                connected_squads=[EU, WL],
                remnawave_id=PANEL_ID,
            )
        )
        await db.commit()
    try:
        yield maker
    finally:
        await engine.dispose()


async def _open(maker, *, strip: bool) -> None:
    from app.services import grace_access_runtime as rt

    async with maker() as db:
        await rt.SQLAlchemyGraceSessionStore(db, subscription_id=42).create(_session(strip=strip))
        await db.commit()


@pytest.mark.asyncio
async def test_renewed_strip_session_holds_the_canonical_write(db_maker, monkeypatch):
    from app.services import grace_access_runtime as rt

    monkeypatch.setattr(rt.settings, 'MULTI_TARIFF_ENABLED', True)
    monkeypatch.setattr(rt.settings, 'SALES_MODE', 'tariffs')
    await _open(db_maker, strip=True)
    async with db_maker() as db:
        assert await rt.strip_grace_holds_canonical(db, 42) is True

        # Докупили трафик — это уже восстановление, канон писать можно.
        sub = await db.get(Subscription, 42)
        sub.traffic_limit_gb = 90
        await db.commit()
        assert await rt.strip_grace_holds_canonical(db, 42) is False


@pytest.mark.asyncio
async def test_classic_grace_and_no_grace_do_not_hold(db_maker, monkeypatch):
    from app.services import grace_access_runtime as rt

    monkeypatch.setattr(rt.settings, 'MULTI_TARIFF_ENABLED', True)
    monkeypatch.setattr(rt.settings, 'SALES_MODE', 'tariffs')
    async with db_maker() as db:
        assert await rt.strip_grace_holds_canonical(db, 42) is False
    await _open(db_maker, strip=False)
    async with db_maker() as db:
        # Обычный grace: продление — это восстановление, путь не меняется.
        assert await rt.strip_grace_holds_canonical(db, 42) is False


def _webhook_sub(*, overlay_at: datetime, end_date: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        status=SubscriptionStatus.ACTIVE.value,
        end_date=end_date,
        pending_panel_expire_at=end_date,
        grace_overlay_expire_at=overlay_at,
        grace_tail_expire_at=None,
        grace_session_open=True,
        traffic_limit_gb=70,
        traffic_used_gb=70.0,
        connected_squads=[EU, WL],
        subscription_url='https://x',
        subscription_crypto_link='crypto',
        updated_at=NOW,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(('panel_is_overlay', 'enqueued'), [(True, False), (False, True)])
async def test_overlay_date_during_grace_is_not_a_failed_renewal(monkeypatch, panel_is_overlay, enqueued):
    import app.services.remnawave_webhook_service as rw
    from app.services.remnawave_retry_queue import remnawave_retry_queue

    overlay_at = END_AT - timedelta(seconds=60)
    panel_expire = overlay_at if panel_is_overlay else END_AT - timedelta(days=3)
    sub = _webhook_sub(overlay_at=overlay_at, end_date=END_AT + timedelta(days=30))

    monkeypatch.setattr(rw, 'get_open_grace_subscription_ids', AsyncMock(return_value={42}))
    monkeypatch.setattr('app.database.crud.transaction.get_last_subscription_payment_at', AsyncMock(return_value=NOW))
    enqueue = MagicMock()
    monkeypatch.setattr(remnawave_retry_queue, 'enqueue', enqueue)

    svc = rw.RemnaWaveWebhookService(MagicMock())
    svc._stamp_webhook_update = MagicMock()
    data = {'expireAt': panel_expire.isoformat(), 'status': 'ACTIVE'}
    await svc._handle_user_modified(AsyncMock(), SimpleNamespace(id=1, telegram_id=1001), sub, data)

    assert enqueue.called is enqueued


async def _close_strip_session(maker, completion: str, *, strip: bool = True) -> None:
    from sqlalchemy import update

    from app.database.models import GraceAccessSessionModel

    await _open(maker, strip=strip)
    async with maker() as db:
        await db.execute(
            update(GraceAccessSessionModel).values(
                state='completed', completion_reason=completion, completed_at=datetime.now(UTC)
            )
        )
        await db.execute(
            update(Subscription)
            .where(Subscription.id == 42)
            .values(status='limited', end_date=datetime.now(UTC) - timedelta(minutes=1), grace_session_open=False)
        )
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('completion', 'strip', 'expired'),
    [('timeout', True, True), ('paid', True, False), ('conflict', True, False), ('timeout', False, False)],
)
async def test_strip_timeout_at_the_end_expires_the_subscription(db_maker, completion, strip, expired):
    """Прод 03.11: после таймаута режима подписка оставалась limited с прошедшей датой —
    мониторинг гасит только active, вебхук user.expired погашен как эхо оверлея, — и
    обычный grace по истечению не выдавался до ночной синхронизации."""
    from app.services import grace_access_runtime as rt

    await _close_strip_session(db_maker, completion, strip=strip)
    async with db_maker() as db:
        changed = await rt._expire_after_strip_timeout(db, 42)
        await db.commit()
    async with db_maker() as db:
        sub = await db.get(Subscription, 42)
    assert changed is expired
    assert (sub.status == 'expired') is expired
    assert (sub.grace_candidate_reason == 'expired') is expired

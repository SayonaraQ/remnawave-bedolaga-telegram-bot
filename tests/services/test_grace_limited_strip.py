"""Grace по трафику без белых списков (GRACE_ACCESS_LIMITED_STRATEGY=strip_squads).

Трафик у оператора считается только на белых списках, поэтому исчерпанный лимит
отключает их одних: остальные сквады подписки остаются, дата — настоящая дата
подписки (минус минута, чтобы дата оверлея оставалась уникальной и защита от
эха работала как прежде), лимит — расход плюс небольшой запас. Возврат белых
списков — только трафиком: докупка или сброс. Продление днями — не возврат,
оверлей переезжает на новую дату.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.services.grace_access_codec import _overlay_from_json, _overlay_to_json, _panel_from_json, _panel_to_json
from app.services.grace_access_service import (
    STRIP_OVERLAY_DATE_OFFSET,
    GraceBillingState,
    GraceCompletionReason,
    GracePanelSnapshot,
    GraceReason,
    GraceSessionState,
    GraceStartDecision,
    billing_has_recovered,
    plan_grace_echo_repair,
)
from tests.services.test_grace_access_service import (
    GIB,
    LIMITED_SQUAD,
    PANEL_ID,
    MutableClock,
    make_policy,
    make_service,
)


MIB = 1024**2
EU_SQUAD = 'aaaaaaaa-0000-0000-0000-000000000001'
PREMIUM_SQUAD = 'aaaaaaaa-0000-0000-0000-000000000002'
WL_SQUAD = 'bbbbbbbb-0000-0000-0000-000000000003'
EXTERNAL = 'cccccccc-0000-0000-0000-000000000004'
NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)
END = NOW + timedelta(days=20)


def strip_policy(**changes):
    return make_policy(
        limited_strategy='strip_squads',
        strip_squad_uuids=frozenset({WL_SQUAD}),
        strip_buffer_bytes=100 * MIB,
        **changes,
    )


def limited_billing(**changes) -> GraceBillingState:
    billing = GraceBillingState(
        subscription_id=42,
        remnawave_id=PANEL_ID,
        status='limited',
        end_at=END,
        traffic_limit_bytes=70 * GIB,
        used_traffic_bytes=70 * GIB,
        device_limit=3,
        squad_uuids=(EU_SQUAD, PREMIUM_SQUAD, WL_SQUAD),
        external_squad_uuid=EXTERNAL,
    )
    return replace(billing, **changes)


def limited_snapshot(**changes) -> GracePanelSnapshot:
    snapshot = GracePanelSnapshot(
        remnawave_id=PANEL_ID,
        status='LIMITED',
        expire_at=END,
        traffic_limit_bytes=70 * GIB,
        used_traffic_bytes=70 * GIB + 5 * MIB,
        squad_uuids=(EU_SQUAD, PREMIUM_SQUAD, WL_SQUAD),
        external_squad_uuid=EXTERNAL,
        traffic_limit_strategy='MONTH',
    )
    return replace(snapshot, **changes)


async def started(policy=None, billing=None, snapshot=None):
    clock = MutableClock(NOW)
    billing = billing or limited_billing()
    service, store, panel, billing_gateway = make_service(
        billing=billing,
        snapshot=snapshot or limited_snapshot(),
        clock=clock,
        policy=policy or strip_policy(),
    )
    result = await service.start_if_eligible(billing, GraceReason.LIMITED)
    return result, service, store, panel, billing_gateway, clock


@pytest.mark.asyncio
async def test_strip_removes_only_whitelist_and_keeps_the_real_date():
    result, _, store, panel, _, _ = await started()

    assert result.decision is GraceStartDecision.STARTED
    overlay = result.session.overlay
    assert overlay.strip_squads is True
    assert overlay.status == 'ACTIVE'
    assert overlay.squad_uuids == (EU_SQUAD, PREMIUM_SQUAD)
    assert overlay.external_squad_uuid == EXTERNAL
    assert overlay.expire_at == END - STRIP_OVERLAY_DATE_OFFSET
    assert overlay.traffic_limit_bytes == 70 * GIB + 5 * MIB + 100 * MIB
    assert result.session.grace_until == overlay.expire_at
    assert panel.applied_overlays == [(PANEL_ID, overlay)]
    assert store.only_session().state is GraceSessionState.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'snapshot_squads',
    [(EU_SQUAD, PREMIUM_SQUAD), (WL_SQUAD,)],
    ids=['nothing_to_strip', 'nothing_left_after_strip'],
)
async def test_strip_falls_back_to_the_grace_squad(snapshot_squads):
    result, *_ = await started(
        billing=limited_billing(squad_uuids=snapshot_squads),
        snapshot=limited_snapshot(squad_uuids=snapshot_squads),
    )

    assert result.session.overlay.strip_squads is False
    assert result.session.overlay.squad_uuids == (LIMITED_SQUAD,)


@pytest.mark.asyncio
async def test_strip_falls_back_when_the_subscription_ends_within_minutes():
    soon = NOW + timedelta(minutes=5)
    result, *_ = await started(
        billing=limited_billing(end_at=soon),
        snapshot=limited_snapshot(expire_at=soon),
    )

    assert result.session.overlay.strip_squads is False


@pytest.mark.asyncio
async def test_default_strategy_is_unchanged():
    result, *_ = await started(policy=make_policy())

    assert result.session.overlay.strip_squads is False
    assert result.session.overlay.squad_uuids == (LIMITED_SQUAD,)


@pytest.mark.asyncio
@pytest.mark.parametrize('renewed_status', ['active', 'limited'])
async def test_renewal_by_days_keeps_the_mode_and_moves_the_date(renewed_status):
    _, service, store, panel, billing_gateway, clock = await started()
    new_end = END + timedelta(days=30)
    billing_gateway.state = limited_billing(end_at=new_end, status=renewed_status)
    clock.advance(timedelta(minutes=1))

    await service.reconcile()

    session = store.only_session()
    assert session.state is GraceSessionState.ACTIVE
    assert session.overlay.expire_at == new_end - STRIP_OVERLAY_DATE_OFFSET
    assert session.grace_until == session.overlay.expire_at
    assert session.billing_before.end_at == new_end
    assert session.overlay.squad_uuids == (EU_SQUAD, PREMIUM_SQUAD)
    assert panel.applied_billing == []
    assert panel.applied_overlays[-1] == (PANEL_ID, session.overlay)

    # Следующие проходы — без конфликта и без новых PATCH.
    applied = len(panel.applied_overlays)
    clock.advance(timedelta(minutes=1))
    await service.reconcile()
    assert store.only_session().state is GraceSessionState.ACTIVE
    assert len(panel.applied_overlays) == applied
    assert panel.applied_billing == []


@pytest.mark.asyncio
async def test_admin_shortening_the_date_is_followed_too():
    _, service, store, _, billing_gateway, clock = await started()
    shorter = END - timedelta(days=5)
    billing_gateway.state = limited_billing(end_at=shorter)

    clock.advance(timedelta(minutes=1))
    await service.reconcile()

    session = store.only_session()
    assert session.state is GraceSessionState.ACTIVE
    assert session.overlay.expire_at == shorter - STRIP_OVERLAY_DATE_OFFSET


@pytest.mark.asyncio
async def test_overlay_date_echoed_into_billing_is_never_followed():
    """Эхо даты оверлея в биллинге не двигает оверлей: иначе каждый проход сдвигал бы дату ещё на минуту."""
    _, service, store, panel, billing_gateway, clock = await started()
    session = store.only_session()
    billing_gateway.state = limited_billing(end_at=session.overlay.expire_at)

    clock.advance(timedelta(minutes=1))
    await service.reconcile()

    assert store.only_session().overlay.expire_at == session.overlay.expire_at
    assert len(panel.applied_overlays) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'recovered',
    [
        dict(status='active', traffic_limit_bytes=90 * GIB),
        dict(status='active', used_traffic_bytes=0),
        dict(status='active', traffic_limit_bytes=0),
    ],
    ids=['traffic_purchase', 'traffic_reset', 'unlimited'],
)
async def test_traffic_brings_the_whitelist_back(recovered):
    _, service, store, panel, billing_gateway, clock = await started()
    billing_gateway.state = limited_billing(**recovered)

    clock.advance(timedelta(minutes=1))
    await service.reconcile()

    session = store.only_session()
    assert session.completion_reason is GraceCompletionReason.PAID
    assert panel.applied_billing[-1].squad_uuids == (EU_SQUAD, PREMIUM_SQUAD, WL_SQUAD)


def test_a_later_date_alone_is_not_recovery_for_strip_sessions():
    session_overlay_end = END - STRIP_OVERLAY_DATE_OFFSET

    class _Session:
        overlay = type('O', (), {'strip_squads': True, 'expire_at': session_overlay_end})()
        billing_before = limited_billing()
        reason = GraceReason.LIMITED

    renewed = limited_billing(status='active', end_at=END + timedelta(days=30))
    assert billing_has_recovered(_Session(), renewed) is False


@pytest.mark.asyncio
async def test_admin_squad_change_is_a_conflict():
    _, service, store, panel, billing_gateway, clock = await started()
    billing_gateway.state = limited_billing(squad_uuids=(EU_SQUAD,))

    clock.advance(timedelta(minutes=1))
    await service.reconcile()

    assert store.only_session().completion_reason is GraceCompletionReason.CONFLICT
    assert panel.applied_billing[-1].squad_uuids == (EU_SQUAD,)


@pytest.mark.asyncio
async def test_subscription_end_restores_the_limited_snapshot_a_minute_early():
    _, service, store, panel, _, clock = await started()

    clock.current = END - timedelta(seconds=30)
    await service.reconcile()

    session = store.only_session()
    assert session.completion_reason is GraceCompletionReason.TIMEOUT
    assert panel.restored_snapshots[-1][1].squad_uuids == (EU_SQUAD, PREMIUM_SQUAD, WL_SQUAD)
    assert panel.restored_snapshots[-1][1].status == 'LIMITED'


@pytest.mark.asyncio
async def test_echo_repair_ignores_strip_sessions():
    """Сквады оверлея «без белых списков» — настоящие сквады подписки, их нельзя «снимать как грейс»."""
    _, _, store, _, _, _ = await started()
    session = store.only_session()

    repair = plan_grace_echo_repair(
        squad_uuids=(EU_SQUAD, PREMIUM_SQUAD),
        traffic_limit_gb=70,
        end_at=session.overlay.expire_at,
        sessions=[session],
        sellable_squads=frozenset(),
    )

    assert repair is None


def test_codec_keeps_the_mode_and_reads_old_rows_as_squad_mode():
    overlay = replace(
        limited_snapshot_overlay := _overlay_from_json(
            {
                'status': 'ACTIVE',
                'expire_at': END.isoformat(),
                'traffic_limit_bytes': 1,
                'squad_uuids': [EU_SQUAD],
                'external_squad_uuid': None,
            }
        ),
        strip_squads=True,
    )
    assert limited_snapshot_overlay.strip_squads is False
    assert _overlay_from_json(_overlay_to_json(overlay)).strip_squads is True

    snapshot = limited_snapshot()
    assert _panel_from_json(_panel_to_json(snapshot)).traffic_limit_strategy == 'MONTH'
    old = _panel_to_json(snapshot)
    old.pop('traffic_limit_strategy')
    assert _panel_from_json(old).traffic_limit_strategy is None


@pytest.mark.asyncio
async def test_follow_survives_a_crash_between_panel_patch_and_save():
    """Панель уже на новой дате, а сессия ещё на старой: досохраняем, без конфликта и без второго PATCH."""
    _, service, store, panel, billing_gateway, clock = await started()
    new_end = END + timedelta(days=30)
    billing_gateway.state = limited_billing(end_at=new_end, status='active')
    panel.snapshot = replace(panel.snapshot, expire_at=new_end - STRIP_OVERLAY_DATE_OFFSET)
    applied = len(panel.applied_overlays)

    clock.advance(timedelta(minutes=1))
    await service.reconcile()

    session = store.only_session()
    assert session.state is GraceSessionState.ACTIVE
    assert session.overlay.expire_at == new_end - STRIP_OVERLAY_DATE_OFFSET
    assert len(panel.applied_overlays) == applied
    assert panel.applied_billing == []

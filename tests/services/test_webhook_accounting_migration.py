"""A panel webhook that lands while traffic accounting is migrating is an echo, not an error.

Migration commits ``migrating`` before it PATCHes the panel to ``NO_RESET``; the
panel answers that PATCH with ``user.modified`` before the second transaction
commits ``managed``. The endpoint always answers 200, so nothing is retried and
the migration re-reads the panel itself. The event must be skipped quietly
instead of reaching the admin error report.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import remnawave_webhook_service as webhook_module
from app.services.remnawave_webhook_service import RemnaWaveWebhookService
from app.services.traffic_accounting import AccountingConflict, AccountingMigrationInProgress


def _service():
    return RemnaWaveWebhookService.__new__(RemnaWaveWebhookService)


def test_migration_in_progress_is_still_an_accounting_conflict():
    # Existing ``except AccountingConflict`` callers must keep catching it.
    assert issubclass(AccountingMigrationInProgress, AccountingConflict)


@pytest.mark.parametrize('handler', ['_handle_user_modified', '_handle_user_traffic_reset'])
async def test_migrating_subscription_raises_migration_in_progress(handler):
    sub = SimpleNamespace(id=481, traffic_accounting_mode='migrating', status='active')
    with pytest.raises(AccountingMigrationInProgress):
        await getattr(_service(), handler)(SimpleNamespace(), SimpleNamespace(id=446), sub, {})


async def _dispatch(monkeypatch, error):
    service = _service()
    user = SimpleNamespace(id=446)
    sub = SimpleNamespace(id=481)
    service._resolve_user_and_subscription = AsyncMock(return_value=(user, sub))
    monkeypatch.setattr(webhook_module.grace_access_runtime, 'should_suppress_webhook', AsyncMock(return_value=False))
    log = MagicMock()
    monkeypatch.setattr(webhook_module, 'logger', log)
    db = SimpleNamespace(rollback=AsyncMock())
    handler = AsyncMock(side_effect=error)
    processed = await service._process_user_event(db, 'user.modified', {}, handler)
    return processed, log, db


async def test_webhook_during_migration_is_skipped_without_error_report(monkeypatch):
    processed, log, db = await _dispatch(
        monkeypatch, AccountingMigrationInProgress('Traffic accounting migration is not complete')
    )
    assert processed is True
    log.exception.assert_not_called()
    log.error.assert_not_called()
    log.info.assert_called_once()
    assert log.info.call_args.kwargs['subscription_id'] == 481
    db.rollback.assert_awaited_once()


async def test_other_accounting_conflicts_are_still_reported(monkeypatch):
    processed, log, db = await _dispatch(monkeypatch, AccountingConflict('Panel account changed during migration'))
    assert processed is False
    log.exception.assert_called_once()
    db.rollback.assert_awaited_once()

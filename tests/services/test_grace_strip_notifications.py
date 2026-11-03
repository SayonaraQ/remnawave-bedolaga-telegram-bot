"""Уведомления режима «без белых списков» (GRACE_ACCESS_LIMITED_STRATEGY=strip_squads).

Человеку — что отключены только белые списки, когда вернутся сами и как вернуть
сразу; при возврате по сбросу — что они снова есть. Админам — только то, что
требует действия: конфликт, отзыв, слив, конец подписки.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from app.cabinet.services.email_templates import EmailNotificationTemplates
from app.database.models import GraceAccessSessionModel, Subscription
from app.services import grace_access_notifications as notify
from app.services.grace_access_service import GraceStartDecision
from app.services.notification_types import NotificationType
from app.services.remnawave_webhook_service import _strip_grace_speaks_for_itself
from tests.services.test_grace_access_notifications import GIB, _seed, lab  # noqa: F401 — фикстура


async def _seed_strip(maker, *, strategy='MONTH', limit_now_gb=50, **kwargs) -> None:
    await _seed(maker, reason='limited', **kwargs)
    async with maker() as db:
        await db.execute(
            update(GraceAccessSessionModel).values(
                overlay={
                    'status': 'ACTIVE',
                    'expire_at': '2026-10-10T11:59:00+00:00',
                    'traffic_limit_bytes': 50 * GIB + 100 * 1024**2,
                    'squad_uuids': ['eu'],
                    'strip_squads': True,
                },
                panel_before={'used_traffic_bytes': 50 * GIB, 'traffic_limit_strategy': strategy},
                billing_before={'traffic_limit_bytes': 50 * GIB},
            )
        )
        await db.execute(update(Subscription).values(traffic_limit_gb=limit_now_gb, status='limited'))
        await db.commit()


def _buttons(kwargs) -> list[str]:
    return [button.text for row in kwargs['telegram_markup'].inline_keyboard for button in row]


@pytest.mark.asyncio
async def test_grant_tells_the_user_about_whitelist_only_with_reset_date(lab):
    await _seed_strip(lab.maker)

    await notify.announce_grace_event(lab.bot, 10, 'granted')

    assert lab.admin.await_count == 0, 'выдача действия от админа не требует'
    kwargs = lab.user.await_args.kwargs
    assert kwargs['notification_type'] is NotificationType.GRACE_ACCESS_GRANTED
    message = kwargs['telegram_message']
    assert 'белых списков' in message
    assert re.search(r'недоступны до 01\.\d\d\.', message), 'MONTH: трафик сбросится 1-го числа'
    assert 'Остальные локации работают' in message
    assert '{' not in message
    assert any('трафик' in label.lower() for label in _buttons(kwargs)), _buttons(kwargs)
    assert kwargs['context']['strip'] is True


@pytest.mark.asyncio
async def test_grant_without_a_monthly_reset_names_no_date(lab):
    await _seed_strip(lab.maker, strategy='NO_RESET')

    await notify.announce_grace_event(lab.bot, 10, 'granted')

    message = lab.user.await_args.kwargs['telegram_message']
    assert 'недоступны.' in message and ' до ' not in message.split('недоступны')[1][:5]


@pytest.mark.asyncio
async def test_reset_ending_tells_the_user_whitelist_is_back(lab):
    await _seed_strip(lab.maker, state='completed', completion_reason='paid')

    await notify.announce_grace_event(lab.bot, 10, 'ended')

    assert lab.admin.await_count == 0
    kwargs = lab.user.await_args.kwargs
    assert kwargs['notification_type'] is NotificationType.GRACE_ACCESS_ENDED
    assert 'снова доступны' in kwargs['telegram_message']
    assert 'обновите подписку' in kwargs['telegram_message']
    assert kwargs['context']['strip_restored'] is True


@pytest.mark.asyncio
async def test_purchase_ending_is_silent(lab):
    """О докупке человек уже получил «трафик добавлен»."""
    await _seed_strip(lab.maker, state='completed', completion_reason='paid', limit_now_gb=70)

    await notify.announce_grace_event(lab.bot, 10, 'ended')

    assert lab.admin.await_count == 0
    assert lab.user.await_count == 0


@pytest.mark.asyncio
async def test_subscription_end_goes_to_admins_only(lab):
    await _seed_strip(lab.maker, state='completed', completion_reason='timeout')

    await notify.announce_grace_event(lab.bot, 10, 'ended')

    assert lab.admin.await_count == 1
    assert lab.user.await_count == 0, 'дальше человеку напишет обычный grace по истечению'


@pytest.mark.asyncio
async def test_conflict_goes_to_admins(lab):
    await _seed_strip(lab.maker, state='completed', completion_reason='conflict', last_error='admin changed squads')

    await notify.announce_grace_event(lab.bot, 10, 'ended')

    assert lab.admin.await_count == 1
    assert lab.user.await_count == 0


@pytest.mark.parametrize(
    ('now', 'expected'),
    [
        (datetime(2026, 11, 3, 12, tzinfo=UTC), '01.12'),
        (datetime(2026, 12, 20, 12, tzinfo=UTC), '01.01'),
        # 30.11 23:30 UTC — уже 1 декабря по Москве: следующий сброс — 1 января.
        (datetime(2026, 11, 30, 23, 30, tzinfo=UTC), '01.01'),
    ],
)
def test_next_monthly_reset_is_the_first_of_next_local_month(now, expected, monkeypatch):
    from zoneinfo import ZoneInfo

    monkeypatch.setattr('app.utils.timezone.get_local_timezone', lambda: ZoneInfo('Europe/Moscow'))
    assert notify.next_traffic_reset_label('MONTH', now=now) == expected
    assert notify.next_traffic_reset_label('NO_RESET', now=now) is None
    assert notify.next_traffic_reset_label(None, now=now) is None


def test_emails_for_users_without_telegram():
    templates = EmailNotificationTemplates()

    granted = templates._grace_access_granted_template(
        'ru', {'strip': True, 'reset_phrase': ' до 01.12', 'tariff_name': 'Базовый'}
    )
    assert granted['subject'] == 'Трафик для белых списков израсходован'
    assert 'до 01.12' in granted['body_html'] and '«Базовый»' in granted['body_html']

    restored = templates._grace_access_ended_template('en', {'strip_restored': True})
    assert restored['subject'] == 'Whitelist locations are back'

    classic = templates._grace_access_granted_template('ru', {'reason': 'limited', 'hours': 72})
    assert classic['subject'] != granted['subject']


def test_limited_webhook_message_is_skipped_only_for_strip_grace(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'GRACE_ACCESS_NOTIFY_USER', True)
    strip = SimpleNamespace(overlay=SimpleNamespace(strip_squads=True))
    classic = SimpleNamespace(overlay=SimpleNamespace(strip_squads=False))

    assert _strip_grace_speaks_for_itself(SimpleNamespace(decision=GraceStartDecision.STARTED, session=strip))
    assert _strip_grace_speaks_for_itself(SimpleNamespace(decision=GraceStartDecision.ALREADY_ACTIVE, session=strip))
    assert not _strip_grace_speaks_for_itself(SimpleNamespace(decision=GraceStartDecision.STARTED, session=classic))
    assert not _strip_grace_speaks_for_itself(SimpleNamespace(decision=GraceStartDecision.NOT_ELIGIBLE, session=None))
    assert not _strip_grace_speaks_for_itself(None)

    monkeypatch.setattr(settings, 'GRACE_ACCESS_NOTIFY_USER', False)
    assert not _strip_grace_speaks_for_itself(SimpleNamespace(decision=GraceStartDecision.STARTED, session=strip))

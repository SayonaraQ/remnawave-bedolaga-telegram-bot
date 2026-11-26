"""Скидка на первое продление (форк, 2026-11): отбор, оффер, кнопка, разовая отправка."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.config import settings
from app.services import monitoring_service
from app.services.monitoring_service import MonitoringService
from app.services.notification_settings_service import NotificationSettingsService


def _service():
    service = MonitoringService.__new__(MonitoringService)
    service.bot = SimpleNamespace(send_message=AsyncMock())
    service._send_message_with_logo = AsyncMock()
    service._log_monitoring_event = AsyncMock()
    return service


def _subscription(*, telegram_id=555, hours_left=70, language='ru'):
    user = SimpleNamespace(id=42, telegram_id=telegram_id, language=language, status='active')
    return SimpleNamespace(
        id=7,
        user_id=42,
        user=user,
        end_date=datetime.now(UTC) + timedelta(hours=hours_left),
        tariff=None,
    )


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, 'FIRST_RENEWAL_DISCOUNT_ENABLED', True)
    monkeypatch.setattr(settings, 'FIRST_RENEWAL_DISCOUNT_PERCENT', 20)
    monkeypatch.setattr(settings, 'FIRST_RENEWAL_DISCOUNT_DAYS_BEFORE', 3)
    monkeypatch.setattr(
        NotificationSettingsService, 'are_notifications_globally_enabled', classmethod(lambda cls: True)
    )
    monkeypatch.setattr('app.utils.notification_prefs.is_promo_offers_enabled', lambda user: True)
    monkeypatch.setattr(monitoring_service, 'get_user_active_promo_discount_percent', lambda user: 0)
    monkeypatch.setattr(monitoring_service, 'notification_sent', AsyncMock(return_value=False))
    record = AsyncMock()
    monkeypatch.setattr(monitoring_service, 'record_notification', record)
    upsert = AsyncMock(return_value=SimpleNamespace(id=9001))
    monkeypatch.setattr(monitoring_service, 'upsert_discount_offer', upsert)
    return SimpleNamespace(record=record, upsert=upsert)


def _flat_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


async def test_disabled_flag_does_nothing(monkeypatch):
    monkeypatch.setattr(settings, 'FIRST_RENEWAL_DISCOUNT_ENABLED', False)
    service = _service()
    service._get_expiring_paid_subscriptions = AsyncMock()
    db = SimpleNamespace(execute=AsyncMock())

    await service._check_first_renewal_discount_offers(db)

    service._get_expiring_paid_subscriptions.assert_not_awaited()
    db.execute.assert_not_awaited()


async def test_one_time_payer_gets_offer_with_claim_button(enabled):
    service = _service()
    subscription = _subscription(hours_left=70)
    service._get_expiring_paid_subscriptions = AsyncMock(return_value=[subscription])
    service._count_paid_subscription_payments = AsyncMock(return_value=1)
    db = SimpleNamespace(rollback=AsyncMock())

    await service._check_first_renewal_discount_offers(db)

    service._get_expiring_paid_subscriptions.assert_awaited_once_with(db, 3)
    kwargs = enabled.upsert.await_args.kwargs
    assert kwargs['notification_type'] == 'first_renewal_discount'
    assert kwargs['discount_percent'] == 20
    assert kwargs['effect_type'] == 'percent_discount'
    assert 69 <= kwargs['valid_hours'] <= 70
    assert kwargs['extra_data'] == {'active_discount_hours': kwargs['valid_hours']}

    send = service._send_message_with_logo.await_args.kwargs
    assert send['chat_id'] == 555
    assert 'скидку 20%' in send['text']
    assert 'через 3 дня' in send['text']
    assert 'VPN' not in send['text']
    callbacks = [b.callback_data for b in _flat_buttons(send['reply_markup']) if b.callback_data]
    assert 'claim_discount_9001' in callbacks
    enabled.record.assert_awaited_once_with(db, 42, 7, 'first_renewal_discount')


@pytest.mark.parametrize('paid_count', [0, 2, 5])
async def test_not_one_time_payer_is_skipped(enabled, paid_count):
    service = _service()
    service._get_expiring_paid_subscriptions = AsyncMock(return_value=[_subscription()])
    service._count_paid_subscription_payments = AsyncMock(return_value=paid_count)

    await service._check_first_renewal_discount_offers(SimpleNamespace(rollback=AsyncMock()))

    enabled.upsert.assert_not_awaited()
    service._send_message_with_logo.assert_not_awaited()


async def test_already_sent_is_skipped(enabled, monkeypatch):
    monkeypatch.setattr(monitoring_service, 'notification_sent', AsyncMock(return_value=True))
    service = _service()
    service._get_expiring_paid_subscriptions = AsyncMock(return_value=[_subscription()])
    service._count_paid_subscription_payments = AsyncMock(return_value=1)

    await service._check_first_renewal_discount_offers(SimpleNamespace(rollback=AsyncMock()))

    enabled.upsert.assert_not_awaited()
    service._send_message_with_logo.assert_not_awaited()


async def test_user_with_active_discount_is_skipped(enabled, monkeypatch):
    monkeypatch.setattr(monitoring_service, 'get_user_active_promo_discount_percent', lambda user: 30)
    service = _service()
    service._get_expiring_paid_subscriptions = AsyncMock(return_value=[_subscription()])
    service._count_paid_subscription_payments = AsyncMock(return_value=1)

    await service._check_first_renewal_discount_offers(SimpleNamespace(rollback=AsyncMock()))

    enabled.upsert.assert_not_awaited()


async def test_email_only_user_is_skipped(enabled):
    service = _service()
    service._get_expiring_paid_subscriptions = AsyncMock(return_value=[_subscription(telegram_id=None)])
    service._count_paid_subscription_payments = AsyncMock(return_value=1)

    await service._check_first_renewal_discount_offers(SimpleNamespace(rollback=AsyncMock()))

    enabled.upsert.assert_not_awaited()


async def test_blocked_bot_is_recorded_and_cycle_continues(enabled):
    service = _service()
    service._send_message_with_logo = AsyncMock(
        side_effect=TelegramForbiddenError(method=SimpleNamespace(), message='bot was blocked by the user')
    )
    service._get_expiring_paid_subscriptions = AsyncMock(return_value=[_subscription()])
    service._count_paid_subscription_payments = AsyncMock(return_value=1)
    db = SimpleNamespace(rollback=AsyncMock())

    await service._check_first_renewal_discount_offers(db)

    enabled.record.assert_awaited_once_with(db, 42, 7, 'first_renewal_discount')
    service._log_monitoring_event.assert_not_awaited()


@pytest.mark.parametrize(
    ('days', 'language', 'expected'),
    [
        (1, 'ru', '1 день'),
        (2, 'ru', '2 дня'),
        (3, 'ru', '3 дня'),
        (5, 'ru', '5 дней'),
        (11, 'ru', '11 дней'),
        (21, 'ru', '21 день'),
        (22, 'ru', '22 дня'),
        (3, 'ua', '3 дні'),
        (1, 'en', '1 day'),
        (3, 'en', '3 days'),
    ],
)
def test_days_text_plural(days, language, expected):
    assert MonitoringService._first_renewal_days_text(days, language) == expected


def test_locale_key_present_and_has_no_vpn_word():
    from app.localization.texts import get_texts

    text = get_texts('ru').get('FIRST_RENEWAL_DISCOUNT_OFFER', '')
    assert '{days_text}' in text and '{percent}' in text
    assert 'VPN' not in text
    for key in (
        'SUBSCRIPTION_EXPIRED_SECOND_WAVE',
        'SUBSCRIPTION_EXPIRED_THIRD_WAVE',
        'PAYMENT_UI_YOOKASSA_SBP_FOOTER',
    ):
        assert 'VPN' not in get_texts('ru').get(key, '')

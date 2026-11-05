"""Поля карточки тарифа и общие преимущества в опциях покупки."""

from types import SimpleNamespace

import pytest

from app.cabinet.routes.subscription_modules import purchase as purchase_routes
from app.database.models import Tariff
from app.services import tariff_purchase_devices
from app.services.system_settings_service import BotConfigurationService


def _tariff(**overrides):
    return Tariff(
        **{
            'id': 3,
            'name': 'Семейный',
            'description': 'Описание для Telegram',
            'is_active': True,
            'is_daily': False,
            'daily_price_kopeks': 0,
            'period_prices': {'30': 30000},
            'traffic_limit_gb': 70,
            'device_limit': 3,
            'device_price_kopeks': 15000,
            'max_device_limit': 10,
            'allowed_squads': [],
            **overrides,
        }
    )


@pytest.fixture
def purchase_options(monkeypatch):
    settings_cls = type(purchase_routes.settings)
    monkeypatch.setattr(settings_cls, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(settings_cls, 'get_sales_mode', lambda self: 'tariffs')
    monkeypatch.setattr(settings_cls, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(purchase_routes.settings, 'MAX_DEVICES_LIMIT', 10)

    async def _no_subscription(db, user_id):
        return None

    async def _recurrent_policy(db, *, user, channel):
        return {'enabled': False}

    monkeypatch.setattr(purchase_routes, 'get_subscription_by_user_id', _no_subscription)
    monkeypatch.setattr(purchase_routes, 'get_cispay_recurrent_policy', _recurrent_policy)

    async def _get_options(tariff, user=None):
        async def _tariffs(db, promo_group_id):
            return [tariff]

        monkeypatch.setattr(purchase_routes, 'get_tariffs_for_user', _tariffs)
        user = user or SimpleNamespace(id=1, balance_kopeks=0, language='ru')
        return await purchase_routes.get_purchase_options(user=user, db=None, subscription_id=None)

    return _get_options


@pytest.mark.asyncio
async def test_purchase_options_exposes_tariff_card_fields(purchase_options):
    fields = {'tagline': 'Для больших файлов', 'speed_limit_mbps': 500, 'has_premium_servers': True}

    response = await purchase_options(_tariff(**fields))

    assert response['sales_mode'] == 'tariffs'
    for field, value in {**fields, 'max_device_limit': 10}.items():
        assert response['tariffs'][0][field] == value


@pytest.mark.asyncio
async def test_purchase_options_legacy_tariff_has_empty_card_fields(purchase_options):
    response = await purchase_options(_tariff())

    assert response['tariffs'][0]['tagline'] is None
    assert response['tariffs'][0]['speed_limit_mbps'] is None
    assert response['tariffs'][0]['has_premium_servers'] is False


@pytest.mark.parametrize(
    ('configured_max', 'base_limit', 'price', 'global_max', 'expected'),
    [
        (10, 3, 15000, 10, 10),
        (None, 3, 15000, 10, 10),
        (0, 3, 15000, 10, 10),
        (10, 3, 0, 10, None),
        (10, 3, -1, 10, None),
        (10, 0, 15000, 10, None),
        (3, 3, 15000, 10, None),
        (2, 3, 15000, 10, None),
        (None, 3, 15000, 3, None),
        (500, 3, 15000, 10, 100),
        (None, 3, 15000, 0, 100),
        (None, 3, 15000, -1, 100),
        (None, 3, 15000, 500, 100),
    ],
)
def test_effective_max_device_limit(monkeypatch, configured_max, base_limit, price, global_max, expected):
    monkeypatch.setattr(tariff_purchase_devices.settings, 'MAX_DEVICES_LIMIT', global_max)
    monkeypatch.setattr(tariff_purchase_devices, 'MAX_DEVICE_LIMIT', 100)
    tariff = _tariff(max_device_limit=configured_max, device_limit=base_limit)

    assert tariff_purchase_devices.effective_max_device_limit(tariff, price) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('overrides', 'expected'),
    [
        ({'max_device_limit': None}, 10),
        ({'device_price_kopeks': 0}, None),
        ({'device_limit': 0}, None),
        ({'max_device_limit': 3}, None),
    ],
)
async def test_purchase_options_exposes_effective_device_ceiling(purchase_options, overrides, expected):
    response = await purchase_options(_tariff(**overrides))

    assert response['tariffs'][0]['max_device_limit'] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(('discount', 'expected_price', 'expected_max'), [(0, 10000, 10), (100, 0, None)])
async def test_device_ceiling_uses_response_price(
    monkeypatch, purchase_options, discount, expected_price, expected_max
):
    monkeypatch.setattr(purchase_routes.settings, 'PRICE_PER_DEVICE', 10000)
    group = SimpleNamespace(id=7, name='Скидка', get_discount_percent=lambda category, days: discount)
    user = SimpleNamespace(id=1, balance_kopeks=0, language='ru', get_primary_promo_group=lambda: group)

    response = await purchase_options(_tariff(device_price_kopeks=None), user=user)

    assert response['tariffs'][0]['device_price_kopeks'] == expected_price
    assert response['tariffs'][0]['max_device_limit'] == expected_max


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('raw', 'expected'), [('globe: Все локации', [{'icon': 'globe', 'text': 'Все локации'}]), ('', [])]
)
async def test_purchase_options_common_features(monkeypatch, purchase_options, raw, expected):
    monkeypatch.setattr(purchase_routes.settings, 'TARIFF_COMMON_FEATURES', raw, raising=False)

    response = await purchase_options(_tariff())

    assert response['common_features'] == expected


def test_common_features_setting_is_registered():
    assert type(purchase_routes.settings).model_fields['TARIFF_COMMON_FEATURES'].default == ''
    assert BotConfigurationService.CATEGORY_KEY_OVERRIDES['TARIFF_COMMON_FEATURES'] == 'SUBSCRIPTIONS_CORE'
    assert 'TARIFF_COMMON_FEATURES' in BotConfigurationService.SETTING_HINTS

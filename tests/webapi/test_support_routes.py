from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.webapi.dependencies import get_db_session


TOKEN = 's' * 48
ALLOWED_HOST = '172.18.0.50'


@pytest.fixture(autouse=True)
def _support_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'SUPPORT_API_TOKEN', TOKEN, raising=False)
    monkeypatch.setattr(settings, 'SUPPORT_API_ALLOWED_IPS', f'{ALLOWED_HOST}/32', raising=False)


def _client(host: str = ALLOWED_HOST) -> TestClient:
    from app.webapi.routes import support

    app = FastAPI()
    app.include_router(support.router, prefix='/support')

    async def _db():
        yield SimpleNamespace()

    app.dependency_overrides[get_db_session] = _db
    return TestClient(app, client=(host, 50000))


def _auth() -> dict[str, str]:
    return {'Authorization': f'Bearer {TOKEN}'}


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        telegram_id=111,
        balance_kopeks=12345,
        email='client@example.com',
        language='ru',
    )


def _subscription(sub_id: int = 10) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=sub_id,
        status='active',
        is_trial=False,
        end_date=now + timedelta(days=20),
        tariff=SimpleNamespace(name='Базовый'),
        tariff_id=3,
        traffic_limit_gb=100,
        traffic_used_gb=12.5,
        purchased_traffic_gb=10,
        traffic_reset_at=now + timedelta(days=10),
        traffic_accounting_mode='managed',
        device_limit=3,
        autopay_enabled=True,
        remnawave_id=4242,
        subscription_url=f'https://sub.example/{sub_id}tokentokentoken',
        subscription_crypto_link='happ://crypt4/secret',
        remnawave_short_uuid='shortuuid',
    )


def _patch_loaders(monkeypatch, *, user, subs=(), grace=frozenset(), open_ticket=False):
    from app.webapi.routes import support

    monkeypatch.setattr(support, '_load_user', AsyncMock(return_value=user))
    monkeypatch.setattr(support, '_load_subscriptions', AsyncMock(return_value=list(subs)))
    monkeypatch.setattr(support, '_open_grace_ids', AsyncMock(return_value=set(grace)))
    monkeypatch.setattr(support, '_has_open_ticket', AsyncMock(return_value=open_ticket))
    return support


@pytest.mark.parametrize('host', ['172.18.0.1', '100.76.105.148'])
def test_card_disallowed_ip_403(monkeypatch, host):
    support = _patch_loaders(monkeypatch, user=_user())
    resp = _client(host).get('/support/card/111', headers=_auth())
    assert resp.status_code == 403
    support._load_user.assert_not_called()


def test_card_missing_token_401(monkeypatch):
    _patch_loaders(monkeypatch, user=_user())
    assert _client().get('/support/card/111').status_code == 401


def test_card_wrong_token_401(monkeypatch):
    _patch_loaders(monkeypatch, user=_user())
    client = _client()
    assert client.get('/support/card/111', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    # a regular Web API token must not open the support router
    assert client.get('/support/card/111', headers={'X-API-Key': 'webapi-token-value'}).status_code == 401


def test_card_x_support_token_header_accepted(monkeypatch):
    _patch_loaders(monkeypatch, user=None)
    assert _client().get('/support/card/111', headers={'X-Support-Token': TOKEN}).status_code == 200


def test_card_token_unset_503(monkeypatch):
    _patch_loaders(monkeypatch, user=_user())
    monkeypatch.setattr(settings, 'SUPPORT_API_TOKEN', None, raising=False)
    assert _client().get('/support/card/111', headers=_auth()).status_code == 503


def test_card_empty_allowlist_denies_all(monkeypatch):
    _patch_loaders(monkeypatch, user=_user())
    monkeypatch.setattr(settings, 'SUPPORT_API_ALLOWED_IPS', '', raising=False)
    assert _client().get('/support/card/111', headers=_auth()).status_code == 403


def test_card_unknown_user(monkeypatch):
    _patch_loaders(monkeypatch, user=None)
    resp = _client().get('/support/card/111', headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body['registered'] is False
    assert body['subscriptions'] == []
    assert body['connect_urls'] == {}
    assert body['telegram_id'] == 111


def test_card_exact_keys(monkeypatch):
    _patch_loaders(monkeypatch, user=_user(), subs=[_subscription(10)], open_ticket=True)
    resp = _client().get('/support/card/111', headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        'telegram_id',
        'registered',
        'balance_kopeks',
        'email_bound',
        'language',
        'has_open_ticket',
        'subscriptions',
        'connect_urls',
    }
    assert set(body['subscriptions'][0]) == {
        'id',
        'status',
        'is_trial',
        'end_date',
        'tariff_name',
        'traffic_limit_gb',
        'traffic_used_gb',
        'purchased_traffic_gb',
        'traffic_reset_at',
        'traffic_accounting_mode',
        'device_limit',
        'autopay_enabled',
        'grace_open',
        'panel_user_id',
    }
    assert body['email_bound'] is True
    assert body['has_open_ticket'] is True
    assert body['subscriptions'][0]['panel_user_id'] == 4242
    assert body['subscriptions'][0]['tariff_name'] == 'Базовый'
    assert body['connect_urls'] == {'10': 'https://sub.example/10tokentokentoken'}
    without_urls = json.dumps({k: v for k, v in body.items() if k != 'connect_urls'})
    for forbidden in ('client@example.com', 'happ://', 'shortuuid', 'tokentokentoken', 'subscription_url'):
        assert forbidden not in without_urls


def test_card_grace_flag(monkeypatch):
    _patch_loaders(monkeypatch, user=_user(), subs=[_subscription(10), _subscription(11)], grace={11})
    body = _client().get('/support/card/111', headers=_auth()).json()
    flags = {s['id']: s['grace_open'] for s in body['subscriptions']}
    assert flags == {10: False, 11: True}


def test_card_telegram_id_not_int_422(monkeypatch):
    _patch_loaders(monkeypatch, user=_user())
    assert _client().get('/support/card/abc', headers=_auth()).status_code == 422


def test_support_routes_mounted_in_app():
    from app.webapi.app import create_web_api_app

    client = TestClient(create_web_api_app(), client=('100.76.105.148', 50000))
    # mounted: a disallowed client gets 403 from the support guard, not 404
    assert client.get('/support/card/111', headers=_auth()).status_code == 403

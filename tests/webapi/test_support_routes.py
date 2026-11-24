from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.config import settings
from app.webapi.dependencies import get_db_session


TOKEN = 's' * 48
ALLOWED_HOST = '172.18.0.50'
MEDIA_PATH = '/support/tickets/5/messages/1/media'


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
    for sub in subs:
        sub.grace_session_open = sub.id in grace
    monkeypatch.setattr(support, '_load_subscriptions', AsyncMock(return_value=list(subs)))
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


# ---------------------------------------------------------------- tickets (Task 3)


def _message(mid: int, from_admin: bool, text: str = 'текст') -> SimpleNamespace:
    return SimpleNamespace(
        id=mid,
        is_from_admin=from_admin,
        message_text=text,
        has_media=False,
        created_at=datetime(2026, 11, 21, 12, mid % 60, tzinfo=UTC),
    )


def _ticket(tid: int = 5) -> SimpleNamespace:
    now = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=tid,
        user=SimpleNamespace(telegram_id=111, email='client@example.com'),
        status='open',
        priority='normal',
        title='Не работает',
        created_at=now,
        updated_at=now,
        messages=[_message(1, False, 'не работает'), _message(2, True, 'проверим'), _message(3, False, 'ещё')],
    )


@pytest.mark.parametrize(
    ('method', 'path', 'body'),
    [
        ('get', '/support/tickets', None),
        ('get', '/support/tickets/5', None),
        ('post', '/support/tickets/5/reply', {'text': 'x'}),
        ('post', '/support/tickets/5/status', {'status': 'open'}),
        ('post', '/support/tickets/5/priority', {'priority': 'high'}),
    ],
)
def test_ticket_routes_require_token(method, path, body):
    client = _client()
    resp = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
    assert resp.status_code == 401


def test_list_maps_user_telegram_id(monkeypatch):
    from app.webapi.routes import support

    monkeypatch.setattr(support, '_load_tickets', AsyncMock(return_value=[_ticket(5)]))
    resp = _client().get('/support/tickets?status=open&limit=50', headers=_auth())
    assert resp.status_code == 200
    item = resp.json()[0]
    assert set(item) == {
        'id',
        'user_telegram_id',
        'status',
        'priority',
        'title',
        'created_at',
        'updated_at',
        'last_message_id',
        'last_message_from_admin',
    }
    assert item['user_telegram_id'] == 111 and item['last_message_id'] == 3 and item['last_message_from_admin'] is False
    support._load_tickets.assert_awaited_once()
    assert 'client@example.com' not in resp.text


def test_get_ticket_with_messages(monkeypatch):
    from app.webapi.routes import support

    monkeypatch.setattr(support, '_load_ticket', AsyncMock(return_value=_ticket(5)))
    body = _client().get('/support/tickets/5', headers=_auth()).json()
    assert [(m['id'], m['is_from_admin'], m['text']) for m in body['messages']] == [
        (1, False, 'не работает'),
        (2, True, 'проверим'),
        (3, False, 'ещё'),
    ]
    assert set(body['messages'][0]) == {'id', 'is_from_admin', 'text', 'has_media', 'created_at', 'attachments'}


def test_get_ticket_missing_404(monkeypatch):
    from app.webapi.routes import support

    monkeypatch.setattr(support, '_load_ticket', AsyncMock(return_value=None))
    assert _client().get('/support/tickets/5', headers=_auth()).status_code == 404


def test_reply_delegates_and_returns_message_id(monkeypatch):
    from app.webapi.routes import support

    fake = AsyncMock(return_value=SimpleNamespace(message=SimpleNamespace(id=77)))
    monkeypatch.setattr(support.tickets, 'reply_to_ticket', fake)
    resp = _client().post('/support/tickets/5/reply', headers=_auth(), json={'text': 'Здравствуйте'})
    assert resp.status_code == 200 and resp.json() == {'message_id': 77}
    kwargs = fake.await_args.kwargs
    assert kwargs['ticket_id'] == 5 and kwargs['payload'].message_text == 'Здравствуйте'


def test_reply_text_too_long_422():
    resp = _client().post('/support/tickets/5/reply', headers=_auth(), json={'text': 'я' * 4001})
    assert resp.status_code == 422


def test_reply_empty_422():
    assert _client().post('/support/tickets/5/reply', headers=_auth(), json={'text': ''}).status_code == 422


def test_status_delegates(monkeypatch):
    from app.webapi.routes import support

    fake = AsyncMock(return_value=None)
    monkeypatch.setattr(support.tickets, 'update_ticket_status', fake)
    resp = _client().post('/support/tickets/5/status', headers=_auth(), json={'status': 'open'})
    assert resp.status_code == 200
    assert fake.await_args.kwargs['payload'].status == 'open'


def test_status_invalid_422():
    assert _client().post('/support/tickets/5/status', headers=_auth(), json={'status': 'deleted'}).status_code == 422


def test_priority_delegates(monkeypatch):
    from app.webapi.routes import support

    fake = AsyncMock(return_value=None)
    monkeypatch.setattr(support.tickets, 'update_ticket_priority', fake)
    resp = _client().post('/support/tickets/5/priority', headers=_auth(), json={'priority': 'high'})
    assert resp.status_code == 200
    assert fake.await_args.kwargs['payload'].priority == 'high'


def test_priority_invalid_422():
    assert _client().post('/support/tickets/5/priority', headers=_auth(), json={'priority': 'max'}).status_code == 422


# ---------------------------------------------------------------- code review 22.11


def test_card_grace_from_subscription_column(monkeypatch):
    # grace runtime in OBSERVE/DISABLED returns no open ids, but the per-row column still knows
    support = _patch_loaders(monkeypatch, user=_user(), subs=[_subscription(10), _subscription(11)])
    monkeypatch.setattr(support, '_open_grace_ids', AsyncMock(return_value=set()), raising=False)
    subs = support._load_subscriptions.return_value
    subs[0].grace_session_open, subs[1].grace_session_open = False, True
    body = _client().get('/support/card/111', headers=_auth()).json()
    assert {s['id']: s['grace_open'] for s in body['subscriptions']} == {10: False, 11: True}


@pytest.mark.asyncio
async def test_has_open_ticket_counts_answered(monkeypatch):
    from app.webapi.routes import support

    monkeypatch.setattr(support.TicketCRUD, 'get_user_tickets', AsyncMock(return_value=[]))
    monkeypatch.setattr(support.TicketCRUD, 'user_has_active_ticket', AsyncMock(return_value=True))
    assert await support._has_open_ticket(None, 7) is True


def test_ticket_detail_lists_album_and_legacy_attachments(monkeypatch):
    from app.webapi.routes import support

    ticket = _ticket(5)
    album = _message(9, False, '')
    album.media_items = [
        {'type': 'photo', 'file_id': 'album-photo'},
        {'type': 'video', 'file_id': 'album-video'},
        {'type': 'document', 'file_id': 'album-document'},
    ]
    legacy = _message(10, False, '')
    legacy.has_media = True
    legacy.media_type = 'photo'
    legacy.media_file_id = 'legacy-photo'
    ticket.messages.extend([album, legacy])
    monkeypatch.setattr(support, '_load_ticket', AsyncMock(return_value=ticket))
    body = _client().get('/support/tickets/5', headers=_auth()).json()
    messages = {message['id']: message for message in body['messages']}
    assert messages[9]['has_media'] is True
    assert messages[9]['attachments'] == [
        {'index': 0, 'type': 'photo'},
        {'index': 1, 'type': 'video'},
        {'index': 2, 'type': 'document'},
    ]
    assert messages[10]['has_media'] is True
    assert messages[10]['attachments'] == [{'index': 0, 'type': 'photo'}]
    assert messages[1]['has_media'] is False
    assert messages[1]['attachments'] == []


@pytest.fixture
def ticket_media(monkeypatch):
    from app.webapi.routes import support

    ticket = _ticket(5)
    ticket.messages[0].media_items = [
        {'type': 'photo', 'file_id': 'client-photo'},
        {'type': 'video', 'file_id': 'client-video'},
        {'type': 'document', 'file_id': 'client-document'},
    ]
    ticket.messages[1].media_items = [{'type': 'photo', 'file_id': 'admin-photo'}]
    other_ticket = _ticket(6)
    other_ticket.messages[0] = _message(9, False)
    other_ticket.messages[0].media_items = [{'type': 'photo', 'file_id': 'other-ticket-photo'}]
    tickets_by_id = {5: ticket, 6: other_ticket}
    load_ticket = AsyncMock(side_effect=lambda db, ticket_id: tickets_by_id.get(ticket_id))
    monkeypatch.setattr(support, '_load_ticket', load_ticket)

    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_size=None, file_path='files/attachment.png')),
        download_file=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )
    create_bot = Mock(return_value=bot)
    monkeypatch.setattr(support, 'create_bot', create_bot)
    return SimpleNamespace(bot=bot, create_bot=create_bot, load_ticket=load_ticket)


@pytest.mark.parametrize(
    ('index', 'file_id', 'data', 'mime'),
    [
        (0, 'client-photo', b'\xff\xd8\xffjpeg-data', 'image/jpeg'),
        (2, 'client-document', b'\x89PNG\r\n\x1a\npng-data', 'image/png'),
        (2, 'client-document', b'RIFF\x04\x00\x00\x00WEBPwebp-data', 'image/webp'),
    ],
    ids=['jpeg-photo', 'png-document', 'webp-document'],
)
def test_ticket_media_returns_image(ticket_media, index, file_id, data, mime):
    bot = ticket_media.bot
    bot.download_file.return_value = BytesIO(data)

    resp = _client().get(f'{MEDIA_PATH}/{index}', headers=_auth())

    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == mime
    assert resp.headers['Cache-Control'] == 'no-store'
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.content == data
    bot.get_file.assert_awaited_once_with(file_id)
    bot.download_file.assert_awaited_once_with('files/attachment.png')
    bot.session.close.assert_awaited_once()


def test_ticket_media_rejects_pdf_with_image_filename(ticket_media):
    bot = ticket_media.bot
    bot.download_file.return_value = BytesIO(b'%PDF-1.7')

    assert _client().get(f'{MEDIA_PATH}/2', headers=_auth()).status_code == 415
    bot.download_file.assert_awaited_once()
    bot.session.close.assert_awaited_once()


def test_ticket_media_rejects_video_before_creating_bot(ticket_media):
    assert _client().get(f'{MEDIA_PATH}/1', headers=_auth()).status_code == 415
    ticket_media.create_bot.assert_not_called()
    ticket_media.bot.download_file.assert_not_called()


@pytest.mark.parametrize(
    ('ticket_id', 'message_id', 'index'),
    [(5, 2, 0), (5, 9, 0), (5, 1, 3), (5, 1, -1), (999, 1, 0)],
    ids=['admin-message', 'other-ticket-message', 'index-too-high', 'negative-index', 'unknown-ticket'],
)
def test_ticket_media_rejects_missing_or_ineligible_attachment(ticket_media, ticket_id, message_id, index):
    path = f'/support/tickets/{ticket_id}/messages/{message_id}/media/{index}'
    assert _client().get(path, headers=_auth()).status_code == 404
    ticket_media.load_ticket.assert_awaited_once_with(ANY, ticket_id)
    ticket_media.create_bot.assert_not_called()


def test_ticket_media_checks_reported_size_before_download(ticket_media):
    bot = ticket_media.bot
    bot.get_file.return_value.file_size = 5_000_001

    assert _client().get(f'{MEDIA_PATH}/0', headers=_auth()).status_code == 413
    bot.download_file.assert_not_called()
    bot.session.close.assert_awaited_once()


def test_ticket_media_checks_download_size_when_reported_size_is_unknown(ticket_media):
    bot = ticket_media.bot
    bot.download_file.return_value = BytesIO(b'\xff\xd8\xff'.ljust(5_000_001, b'\x00'))

    assert _client().get(f'{MEDIA_PATH}/0', headers=_auth()).status_code == 413
    bot.download_file.assert_awaited_once()
    bot.session.close.assert_awaited_once()


def test_ticket_media_handles_telegram_error(ticket_media):
    bot = ticket_media.bot
    private_detail = 'client-photo private-bot-token'
    bot.get_file.side_effect = RuntimeError(private_detail)

    with capture_logs() as logs:
        resp = _client().get(f'{MEDIA_PATH}/0', headers=_auth())

    assert resp.status_code == 502
    assert resp.json() == {'detail': 'Failed to download ticket media'}
    warnings = [event for event in logs if event['log_level'] == 'warning']
    assert len(warnings) == 1
    warning = warnings[0]
    assert {key: value for key, value in warning.items() if key not in {'event', 'log_level'}} == {
        'ticket_id': 5,
        'message_id': 1,
        'index': 0,
        'error_type': 'RuntimeError',
    }
    assert all(secret not in warning['event'] for secret in private_detail.split())
    bot.download_file.assert_not_called()
    bot.session.close.assert_awaited_once()


def test_ticket_media_times_out_during_download(monkeypatch, ticket_media):
    from app.webapi.routes import support

    async def download_file(file_path):
        await asyncio.sleep(0)
        return BytesIO(b'\xff\xd8\xffjpeg-data')

    timeout = Mock(side_effect=lambda seconds: asyncio.timeout(0))
    monkeypatch.setattr(support, 'asyncio', SimpleNamespace(timeout=timeout))
    bot = ticket_media.bot
    bot.download_file.side_effect = download_file

    assert _client().get(f'{MEDIA_PATH}/0', headers=_auth()).status_code == 502
    timeout.assert_called_once_with(20)
    bot.download_file.assert_awaited_once()
    bot.session.close.assert_awaited_once()


@pytest.mark.parametrize(
    ('host', 'headers', 'expected_status'),
    [(ALLOWED_HOST, {}, 401), ('172.18.0.1', _auth(), 403)],
    ids=['missing-token', 'disallowed-ip'],
)
def test_ticket_media_requires_token_and_allowed_ip(ticket_media, host, headers, expected_status):
    assert _client(host).get(f'{MEDIA_PATH}/0', headers=headers).status_code == expected_status
    ticket_media.load_ticket.assert_not_called()
    ticket_media.create_bot.assert_not_called()

"""Поля карточки тарифа сохраняются и очищаются через админский API."""

import pytest

from app.database.models import Tariff
from tests.cabinet.test_admin_create_update_schema_parity import _app, _tariff_payload


CARD_FIELDS = {'tagline': 'Для всей семьи', 'speed_limit_mbps': 50, 'has_premium_servers': True}


@pytest.mark.asyncio
async def test_create_tariff_saves_card_fields(monkeypatch):
    async with _app(monkeypatch) as (http, db):
        response = http.post('/cabinet/admin/tariffs', json=_tariff_payload(**CARD_FIELDS))

        assert response.status_code == 200, response.text
        tariff_id = response.json()['id']
        detail = http.get(f'/cabinet/admin/tariffs/{tariff_id}')
        assert detail.status_code == 200, detail.text
        stored = await db.get(Tariff, tariff_id)
        for field, value in CARD_FIELDS.items():
            assert response.json()[field] == value
            assert detail.json()[field] == value
            assert getattr(stored, field) == value


@pytest.mark.asyncio
async def test_create_tariff_without_card_fields_uses_defaults(monkeypatch):
    async with _app(monkeypatch) as (http, db):
        response = http.post('/cabinet/admin/tariffs', json=_tariff_payload())

        assert response.status_code == 200, response.text
        stored = await db.get(Tariff, response.json()['id'])
        for field, value in {'tagline': None, 'speed_limit_mbps': None, 'has_premium_servers': False}.items():
            assert response.json()[field] == value
            assert getattr(stored, field) == value


@pytest.mark.asyncio
async def test_update_tariff_null_clears_tagline_and_speed(monkeypatch):
    async with _app(monkeypatch) as (http, db):
        tariff_id = http.post('/cabinet/admin/tariffs', json=_tariff_payload(**CARD_FIELDS)).json()['id']

        response = http.put(f'/cabinet/admin/tariffs/{tariff_id}', json={'tagline': None, 'speed_limit_mbps': None})

        assert response.status_code == 200, response.text
        assert response.json()['tagline'] is None
        assert response.json()['speed_limit_mbps'] is None
        assert response.json()['has_premium_servers'] is True
        stored = await db.get(Tariff, tariff_id)
        assert stored.tagline is None
        assert stored.speed_limit_mbps is None


@pytest.mark.asyncio
async def test_update_tariff_without_card_fields_keeps_them(monkeypatch):
    async with _app(monkeypatch) as (http, db):
        tariff_id = http.post('/cabinet/admin/tariffs', json=_tariff_payload(**CARD_FIELDS)).json()['id']

        response = http.put(f'/cabinet/admin/tariffs/{tariff_id}', json={'name': 'x'})

        assert response.status_code == 200, response.text
        stored = await db.get(Tariff, tariff_id)
        for field, value in CARD_FIELDS.items():
            assert response.json()[field] == value
            assert getattr(stored, field) == value


@pytest.mark.asyncio
@pytest.mark.parametrize(('tagline', 'expected'), [('   ', None), ('  Для семьи ', 'Для семьи')])
async def test_update_tariff_blank_tagline_becomes_none(monkeypatch, tagline, expected):
    async with _app(monkeypatch) as (http, db):
        tariff_id = http.post('/cabinet/admin/tariffs', json=_tariff_payload(**CARD_FIELDS)).json()['id']

        response = http.put(f'/cabinet/admin/tariffs/{tariff_id}', json={'tagline': tagline})

        assert response.status_code == 200, response.text
        assert response.json()['tagline'] == expected
        assert (await db.get(Tariff, tariff_id)).tagline == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(('tagline', 'expected'), [('   ', None), ('  Для семьи ', 'Для семьи')])
async def test_create_tariff_normalizes_tagline(monkeypatch, tagline, expected):
    async with _app(monkeypatch) as (http, db):
        response = http.post('/cabinet/admin/tariffs', json=_tariff_payload(tagline=tagline))

        assert response.status_code == 200, response.text
        assert response.json()['tagline'] == expected
        assert (await db.get(Tariff, response.json()['id'])).tagline == expected


@pytest.mark.asyncio
async def test_update_tariff_changes_speed_and_premium_flag(monkeypatch):
    async with _app(monkeypatch) as (http, db):
        tariff_id = http.post('/cabinet/admin/tariffs', json=_tariff_payload(**CARD_FIELDS)).json()['id']

        response = http.put(
            f'/cabinet/admin/tariffs/{tariff_id}', json={'speed_limit_mbps': 500, 'has_premium_servers': False}
        )

        assert response.status_code == 200, response.text
        assert response.json()['speed_limit_mbps'] == 500
        assert response.json()['has_premium_servers'] is False
        stored = await db.get(Tariff, tariff_id)
        assert stored.speed_limit_mbps == 500
        assert stored.has_premium_servers is False


@pytest.mark.asyncio
@pytest.mark.parametrize('speed', [0, 100001])
async def test_speed_limit_validation(monkeypatch, speed):
    async with _app(monkeypatch) as (http, _db):
        response = http.post('/cabinet/admin/tariffs', json=_tariff_payload(speed_limit_mbps=speed))
        assert response.status_code == 422, response.text

        tariff_id = http.post('/cabinet/admin/tariffs', json=_tariff_payload()).json()['id']
        response = http.put(f'/cabinet/admin/tariffs/{tariff_id}', json={'speed_limit_mbps': speed})
        assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_tagline_length_validation(monkeypatch):
    async with _app(monkeypatch) as (http, _db):
        response = http.post('/cabinet/admin/tariffs', json=_tariff_payload(tagline='x' * 161))
        assert response.status_code == 422, response.text

        tariff_id = http.post('/cabinet/admin/tariffs', json=_tariff_payload()).json()['id']
        response = http.put(f'/cabinet/admin/tariffs/{tariff_id}', json={'tagline': 'x' * 161})
        assert response.status_code == 422, response.text

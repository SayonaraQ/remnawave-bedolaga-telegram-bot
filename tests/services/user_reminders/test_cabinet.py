from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.database.models import Base, User, UserReminder
from app.services.user_reminders import cabinet as cabinet_service
from app.services.user_reminders.cabinet import active_cards_for_user, dismiss_reminder
from tests.fixtures.sqlite_memory import memory_session


NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
TABLES = list(Base.metadata.sorted_tables)
TEXTS = {'ru': {'title': 'Привет', 'body': 'Текст', 'button': 'Открыть'}, 'en': {'title': 'Hi', 'body': 'Body'}}
BROKEN_TEXTS = {'en': {'title': 't', 'body': 'b'}}


def _reminder(rid, **kw):
    base = dict(
        id=rid,
        name=f'r{rid}',
        channels='cabinet',
        category='service',
        conditions={},
        repeat_every_days=7,
        max_sends=1,
        texts=TEXTS,
        button_kind='cabinet',
        button_target='/profile/accounts',
        is_active=True,
    )
    base.update(kw)
    return UserReminder(**base)


async def _seed(db, reminders):
    db.add(
        User(
            id=1,
            telegram_id=10,
            first_name='U',
            language='ru',
            status='active',
            balance_kopeks=0,
            created_at=NOW - timedelta(days=30),
        )
    )
    db.add_all(reminders)
    await db.commit()
    return await db.get(User, 1)


@pytest.mark.asyncio
async def test_cards_follow_conditions_channels_and_order(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(
            db,
            [
                _reminder(1),
                _reminder(2, builtin_key='k'),
                _reminder(3, channels='bot'),
                _reminder(4, is_active=False),
                _reminder(5, conditions={'auth': 'email_only'}),
            ],
        )
        cards = await active_cards_for_user(db, user, lang='en', now=NOW)

    assert [card['id'] for card in cards] == [2, 1]
    assert cards[0] == {
        'id': 2,
        'title': 'Hi',
        'body': 'Body',
        'button': {'kind': 'cabinet', 'target': '/profile/accounts', 'text': 'Открыть'},
    }


@pytest.mark.asyncio
async def test_dismissed_card_is_gone_and_dismiss_is_idempotent(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, [_reminder(1)])
        assert await dismiss_reminder(db, user, 1, now=NOW) is True
        assert await dismiss_reminder(db, user, 1, now=NOW + timedelta(hours=1)) is True
        assert await active_cards_for_user(db, user, lang='ru', now=NOW) == []


@pytest.mark.asyncio
async def test_dismissed_card_returns_after_repeat_window(monkeypatch):
    """Крестик прячет карточку на repeat_every_days, отсчёт — от последнего закрытия."""
    day = timedelta(days=1)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, [_reminder(1, repeat_every_days=1)])
        assert await dismiss_reminder(db, user, 1, now=NOW) is True
        assert await active_cards_for_user(db, user, lang='ru', now=NOW + timedelta(hours=23)) == []
        assert [c['id'] for c in await active_cards_for_user(db, user, lang='ru', now=NOW + day)] == [1]

        assert await dismiss_reminder(db, user, 1, now=NOW + day + timedelta(hours=1)) is True
        assert await active_cards_for_user(db, user, lang='ru', now=NOW + 2 * day) == []
        assert [
            c['id'] for c in await active_cards_for_user(db, user, lang='ru', now=NOW + 2 * day + timedelta(hours=1))
        ] == [1]


@pytest.mark.asyncio
async def test_link_cards_never_reach_people_with_telegram_and_email(monkeypatch):
    """«Подключите Telegram» — всем без Telegram, «Добавьте почту» — только Telegram;
    у кого есть и то и другое, не видит ни одну, сколько бы дней ни прошло."""
    users = {
        'tg_and_email': dict(telegram_id=10, email='a@x', password_hash='h'),
        'tg_and_google': dict(telegram_id=11, google_id='g1'),
        'tg_only': dict(telegram_id=12),
        'email_only': dict(email='b@x', password_hash='h'),
        'google_only': dict(google_id='g2'),
        'yandex_and_email': dict(yandex_id='y', email='c@x', password_hash='h'),
    }
    expected = {
        'tg_and_email': [],
        'tg_and_google': [],
        'tg_only': [2],
        'email_only': [1],
        'google_only': [1],
        'yandex_and_email': [1],
    }
    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(
            [
                _reminder(1, conditions={'auth': 'no_telegram'}, repeat_every_days=1),
                _reminder(2, conditions={'auth': 'telegram_only'}, repeat_every_days=1),
            ]
        )
        for uid, (name, fields) in enumerate(users.items(), start=1):
            db.add(
                User(
                    id=uid,
                    username=name,
                    first_name='U',
                    language='ru',
                    status='active',
                    balance_kopeks=0,
                    created_at=NOW - timedelta(days=30),
                    **fields,
                )
            )
        await db.commit()
        for uid, name in enumerate(users, start=1):
            user = await db.get(User, uid)
            for when in (NOW, NOW + timedelta(days=30)):
                cards = await active_cards_for_user(db, user, lang='ru', now=when)
                assert [c['id'] for c in cards] == expected[name], name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('start', 'linked', 'reminder_id'),
    [
        (dict(email='b@x', password_hash='h'), dict(telegram_id=21), 1),
        (dict(google_id='g'), dict(telegram_id=22), 1),
        (dict(telegram_id=23), dict(email='c@x', password_hash='h'), 2),
    ],
    ids=['email_then_telegram', 'google_then_telegram', 'telegram_then_email'],
)
async def test_closed_card_stays_gone_after_second_method_is_linked(monkeypatch, start, linked, reminder_id):
    """Закрыл карточку, потом привязал второй способ входа: окно повтора истекает, а карточка
    не возвращается — ни в кабинете, ни в отборе бота (тот же набор условий в SQL)."""
    from sqlalchemy import select

    from app.services.user_reminders.conditions import condition_clauses, parse_conditions

    conditions = {1: {'auth': 'no_telegram'}, 2: {'auth': 'telegram_only'}}
    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all([_reminder(rid, conditions=c, repeat_every_days=1) for rid, c in conditions.items()])
        db.add(
            User(
                id=1,
                first_name='U',
                language='ru',
                status='active',
                balance_kopeks=0,
                created_at=NOW - timedelta(days=30),
                **start,
            )
        )
        await db.commit()
        user = await db.get(User, 1)

        assert [c['id'] for c in await active_cards_for_user(db, user, lang='ru', now=NOW)] == [reminder_id]
        assert await dismiss_reminder(db, user, reminder_id, now=NOW) is True

        for field, value in linked.items():
            setattr(user, field, value)
        await db.commit()

        for later in (timedelta(days=1, minutes=1), timedelta(days=30)):
            assert await active_cards_for_user(db, user, lang='ru', now=NOW + later) == []
            for rid, c in conditions.items():
                clauses = condition_clauses(parse_conditions(c), now=NOW + later)
                assert (await db.execute(select(User.id).where(*clauses))).scalars().all() == [], rid


@pytest.mark.asyncio
@pytest.mark.parametrize('reminder_kw', [{'is_active': False}, {'channels': 'bot'}])
async def test_dismiss_unknown_or_not_for_cabinet_is_false(monkeypatch, reminder_kw):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, [_reminder(1, **reminder_kw)])
        assert await dismiss_reminder(db, user, 1, now=NOW) is False
        assert await dismiss_reminder(db, user, 999, now=NOW) is False


@pytest.mark.asyncio
async def test_broken_conditions_do_not_break_the_page(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, [_reminder(1, conditions={'auth': 'garbage'}), _reminder(2)])
        cards = await active_cards_for_user(db, user, lang='ru', now=NOW)
    assert [card['id'] for card in cards] == [2]


@pytest.mark.asyncio
async def test_broken_texts_do_not_break_the_page(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, [_reminder(1, texts=BROKEN_TEXTS), _reminder(2)])
        cards = await active_cards_for_user(db, user, lang='ru', now=NOW)
    assert [card['id'] for card in cards] == [2]


@pytest.mark.asyncio
async def test_dismiss_returns_false_when_state_cannot_be_created(monkeypatch):
    """get_or_create_state вернёт None при FK-гонке (напоминание/юзер удалены между
    проверкой и вставкой) — dismiss_reminder не должен падать AttributeError, роут
    превращает False в 404.
    """
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, [_reminder(1)])
        monkeypatch.setattr(cabinet_service, 'get_or_create_state', AsyncMock(return_value=None))

        assert await dismiss_reminder(db, user, 1, now=NOW) is False

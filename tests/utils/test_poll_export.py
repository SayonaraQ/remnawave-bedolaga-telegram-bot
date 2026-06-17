"""Тесты построения CSV-выгрузки ответов на опрос (кто как ответил)."""

import csv
import io
from datetime import UTC, datetime
from types import SimpleNamespace

from app.utils.poll_export import build_poll_responses_csv


def _question(question_id: int, text: str, order: int = 0):
    return SimpleNamespace(id=question_id, text=text, order=order)


def _answer(question_id: int, option_text: str):
    return SimpleNamespace(question_id=question_id, option=SimpleNamespace(text=option_text))


def _response(user, completed_at, answers):
    return SimpleNamespace(user=user, completed_at=completed_at, answers=answers)


def test_csv_header_and_maps_answers_to_question_columns():
    # Questions intentionally out of order to verify sorting by `order`.
    q_quality = _question(1, 'Качество сервиса?', order=0)
    q_recommend = _question(2, 'Рекомендуете, да?', order=1)  # запятая в тексте -> проверка CSV-экранирования
    poll = SimpleNamespace(title='Опрос', questions=[q_recommend, q_quality])

    user = SimpleNamespace(id=10, telegram_id=555, username='alice')
    response = _response(
        user,
        datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        [_answer(1, 'Плохо'), _answer(2, 'Нет')],
    )

    csv_text = build_poll_responses_csv(poll, [response])
    rows = list(csv.reader(io.StringIO(csv_text)))

    assert rows[0] == [
        'user_id',
        'telegram_id',
        'username',
        'completed_at',
        'Качество сервиса?',
        'Рекомендуете, да?',
    ]
    assert rows[1][:3] == ['10', '555', 'alice']
    # Ответы должны попасть в колонку своего вопроса независимо от порядка в answers.
    assert rows[1][4] == 'Плохо'
    assert rows[1][5] == 'Нет'


def test_incomplete_responses_are_skipped_and_missing_username_is_blank():
    q = _question(1, 'Вопрос', order=0)
    poll = SimpleNamespace(title='Опрос', questions=[q])

    completed = _response(
        SimpleNamespace(id=1, telegram_id=2, username=None),
        datetime(2026, 6, 1, tzinfo=UTC),
        [_answer(1, 'Ответ')],
    )
    pending = _response(
        SimpleNamespace(id=3, telegram_id=4, username='bob'),
        None,  # приглашён, но не завершил -> в выгрузку не попадает
        [],
    )

    csv_text = build_poll_responses_csv(poll, [pending, completed])
    rows = list(csv.reader(io.StringIO(csv_text)))

    assert len(rows) == 2  # заголовок + одна завершённая строка
    assert rows[1][0] == '1'
    assert rows[1][2] == ''  # username=None -> пустая ячейка
    assert rows[1][4] == 'Ответ'

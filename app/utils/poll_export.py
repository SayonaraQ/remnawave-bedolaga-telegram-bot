"""Построение CSV-выгрузки ответов на опрос (кто как ответил).

Чистая функция без обращений к БД/Telegram: на вход принимает уже загруженный
опрос с вопросами и список ответов с предзагруженными связями, на выход —
CSV-текст. Это держит логику тестируемой и не привязанной к инфраструктуре.
"""

from __future__ import annotations

import csv
import io
from typing import Any

_BASE_COLUMNS = ['user_id', 'telegram_id', 'username', 'completed_at']


def build_poll_responses_csv(poll: Any, responses: list[Any]) -> str:
    """Вернуть CSV с одной строкой на КАЖДЫЙ завершённый ответ.

    Колонки: user_id, telegram_id, username, completed_at, затем по одной колонке
    на каждый вопрос опроса (значение — выбранный вариант). Незавершённые ответы
    (`completed_at is None` — приглашён, но не прошёл) пропускаются.
    """
    questions = sorted(poll.questions, key=lambda question: question.order)
    header = _BASE_COLUMNS + [question.text for question in questions]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)

    for response in responses:
        if response.completed_at is None:
            continue

        answer_by_question = {
            answer.question_id: (answer.option.text if answer.option else '')
            for answer in response.answers
        }

        user = response.user
        row = [
            getattr(user, 'id', '') or '',
            getattr(user, 'telegram_id', '') or '',
            getattr(user, 'username', None) or '',
            response.completed_at.isoformat() if response.completed_at else '',
        ]
        row.extend(answer_by_question.get(question.id, '') for question in questions)
        writer.writerow(row)

    return buffer.getvalue()

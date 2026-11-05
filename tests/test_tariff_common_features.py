"""Разбор настройки общего блока преимуществ тарифов."""

import pytest


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        (
            'globe: Все локации\nyoutube: YouTube без рекламы',
            [{'icon': 'globe', 'text': 'Все локации'}, {'icon': 'youtube', 'text': 'YouTube без рекламы'}],
        ),
        (
            'plus: Устройства; check: Поддержка',
            [{'icon': 'plus', 'text': 'Устройства'}, {'icon': 'check', 'text': 'Поддержка'}],
        ),
        ('Просто текст', [{'icon': 'check', 'text': 'Просто текст'}]),
        ('rocket: Быстро', [{'icon': 'check', 'text': 'rocket: Быстро'}]),
        ('  GLOBE : Мир  ', [{'icon': 'globe', 'text': 'Мир'}]),
        ('infinity: Безлимит', [{'icon': 'infinity', 'text': 'Безлимит'}]),
        ('check: Адрес: порт', [{'icon': 'check', 'text': 'Адрес: порт'}]),
        ('  rocket: Быстро  ', [{'icon': 'check', 'text': 'rocket: Быстро'}]),
        (None, []),
        ('', []),
        ('  ;\n ', []),
        ('globe: ;check: \n youtube: ', []),
        (';\n'.join(f'Пункт {i}' for i in range(10)), [{'icon': 'check', 'text': f'Пункт {i}'} for i in range(8)]),
        ('\n;globe: ;' * 10 + 'plus: Устройства', [{'icon': 'plus', 'text': 'Устройства'}]),
        ('check: ' + 'я' * 100, [{'icon': 'check', 'text': 'я' * 80}]),
        ('check: ' + 'я' * 79 + ' ' + 'б' * 20, [{'icon': 'check', 'text': 'я' * 79}]),
    ],
)
def test_parse_tariff_common_features(raw, expected):
    from app.utils.tariff_common_features import parse_tariff_common_features

    assert parse_tariff_common_features(raw) == expected

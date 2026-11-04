"""Имя приложения-клиента из User-Agent, с которым устройство пришло за подпиской.

Кабинет показывает его в слоте устройства: один телефон с подпиской в INCY и
в Happ — это два HWID и два слота, и без имени приложения человек видит два
одинаковых «Xiaomi 14» и не понимает, откуда второй.
"""

import pytest

from app.utils.client_app import client_app_from_user_agent


@pytest.mark.parametrize(
    ('user_agent', 'expected'),
    [
        ('Happ/3.12.1/ios/7DC77607-4D15-921F-B944-6FB19978F86A', 'Happ'),
        ('INCY/3.7.0', 'INCY'),
        ('v2raytun/android', 'v2raytun'),
        ('koala-clash/0.4.2', 'koala-clash'),
        ('FlClash X/1.0', 'FlClash X'),
        ('  Happ/3.0 ', 'Happ'),
        ('sing-box', 'sing-box'),
    ],
)
def test_takes_the_product_token(user_agent: str, expected: str) -> None:
    assert client_app_from_user_agent(user_agent) == expected


@pytest.mark.parametrize('user_agent', [None, '', '   ', '/1.0'])
def test_returns_none_when_nothing_to_show(user_agent: str | None) -> None:
    assert client_app_from_user_agent(user_agent) is None


def test_caps_length() -> None:
    assert client_app_from_user_agent('x' * 200 + '/1.0') == 'x' * 40

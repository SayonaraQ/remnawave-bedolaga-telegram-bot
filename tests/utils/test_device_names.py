"""Человеческое имя Android-устройства по коду модели.

Клиенты присылают в панель код модели: Happ — «25102PCBEG», INCY — «Xiaomi
25102PCBEG». Человек же знает свой телефон как «POCO F8 Ultra». Пары взяты из
панели 04.11.2026 и справочника Google Play.
"""

import pytest

from app.utils.device_names import marketing_name


@pytest.mark.parametrize(
    ('platform', 'model', 'expected'),
    [
        ('Android', '25102PCBEG', 'POCO F8 Ultra'),
        ('Android', 'Xiaomi 25102PCBEG', 'POCO F8 Ultra'),
        ('Android', 'M2102J20SG', 'POCO X3 Pro'),
        ('Android', 'SM-A556E', 'Samsung Galaxy A55 5G'),
        ('Android', 'samsung SM-A556E', 'Samsung Galaxy A55 5G'),
        ('Android', 'BRP-NX1', 'HONOR X9c'),
        ('Android', 'CPH2653', 'OnePlus 13'),
        ('android', 'TECNO TECNO BG7n', 'TECNO SPARK 20C'),
    ],
)
def test_translates_model_codes(platform: str, model: str, expected: str) -> None:
    assert marketing_name(platform, model) == expected


@pytest.mark.parametrize(
    ('platform', 'model'),
    [
        # Последнее слово без цифр ничего не значит: «ATV» дало бы «Smart ATV device».
        ('Android', 'Amlogic W2 ATV'),
        # Уже человеческое имя — переводить нечего.
        ('Android', 'Pixel 7 Pro'),
        ('iOS', 'iPhone 17 Pro'),
        # У компьютеров в модели версия системы, а не машина.
        ('Windows', 'Windows 11 Pro'),
        ('Android', ''),
        ('Android', None),
        ('Android', 'Unknown'),
    ],
)
def test_leaves_names_it_cannot_improve(platform: str, model: str | None) -> None:
    assert marketing_name(platform, model) is None

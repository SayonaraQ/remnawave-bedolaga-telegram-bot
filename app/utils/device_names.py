"""Человеческое имя Android-устройства по коду модели.

Клиенты VPN присылают в панель код модели: Happ — «25102PCBEG», INCY —
«Xiaomi 25102PCBEG», v2RayTun — «POCO M2102J20SG». Человек знает свой телефон
как «POCO F8 Ultra», и в кабинете код ему ничего не говорит.

Справочник — `device_names.json.gz` рядом, собранный из списка устройств Google
Play скриптом `scripts/update_device_names.py`. На 04.11.2026 он узнаёт 89 %
Android-устройств в нашей панели. iPhone и компьютеры не трогаем: iOS-клиенты
и так пишут «iPhone 17 Pro», а у компьютеров в модели версия системы.
"""

from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path


_DATA = Path(__file__).with_name('device_names.json.gz')


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    # Справочник декоративный: без него кабинет просто покажет код модели.
    try:
        with gzip.open(_DATA, 'rt', encoding='utf-8') as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def _clean(model: str) -> str:
    """«TECNO TECNO BG7n» → «tecno bg7n»: часть клиентов пишет бренд дважды."""
    tokens = model.strip().lower().split()
    if len(tokens) >= 2 and tokens[0] == tokens[1]:
        tokens.pop(1)
    return ' '.join(tokens)


def marketing_name(platform: str | None, model: str | None) -> str | None:
    if not platform or not model or 'android' not in platform.lower():
        return None
    cleaned = _clean(model)
    if not cleaned or cleaned == 'unknown':
        return None
    tokens = cleaned.split()
    # Целиком, без бренда спереди («xiaomi 25102pcbeg» → «25102pcbeg»), последний токен.
    candidates = [cleaned]
    if len(tokens) > 1:
        candidates += [' '.join(tokens[1:]), tokens[-1]]
    names = _names()
    for candidate in candidates:
        # Без цифр совпадение ничего не значит: «atv» дало бы «Smart ATV device».
        if any(ch.isdigit() for ch in candidate) and candidate in names:
            return names[candidate]
    return None

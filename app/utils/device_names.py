"""Человеческое имя Android-устройства по коду модели.

Клиенты VPN присылают в панель код модели: Happ — «25102PCBEG», INCY —
«Xiaomi 25102PCBEG», v2RayTun — «POCO M2102J20SG». Человек знает свой телефон
как «POCO F8 Ultra», и в кабинете код ему ничего не говорит.

Справочник собирается из списка устройств Google Play. Два источника:
- `data/device_names.json.gz` — свежий, бот сам перекачивает его раз в месяц
  (`app/services/device_names_refresh.py`), папка data переживает пересборку;
- `device_names.json.gz` рядом с модулем — вшитый в образ, запасной.
Свежий файл подхватывается без перезапуска: кеш сверяется с временем изменения.

На 04.11.2026 справочник узнаёт 89 % Android-устройств в нашей панели. iPhone и
компьютеры не трогаем: iOS-клиенты и так пишут «iPhone 17 Pro», а у компьютеров
в модели версия системы.
"""

from __future__ import annotations

import collections
import csv
import gzip
import io
import json
from pathlib import Path


BUNDLED_PATH = Path(__file__).with_name('device_names.json.gz')
REFRESHED_PATH = Path('data') / 'device_names.json.gz'

_cache: dict[str, object] = {'key': None, 'names': {}}


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    """Список Google Play приходит в UTF-16 с BOM; на всякий случай понимаем и UTF-8."""
    text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8')
    return list(csv.DictReader(io.StringIO(text)))


def build_names(rows: list[dict[str, str]]) -> dict[str, str]:
    """Код модели (нижний регистр) → название с брендом («Samsung Galaxy A55 5G»)."""
    names: dict[str, collections.Counter[str]] = {}
    for row in rows:
        model = (row.get('Model') or '').strip()
        marketing = (row.get('Marketing Name') or '').strip()
        brand = (row.get('Retail Branding') or '').strip()
        # Без цифр в коде совпадение ничего не значит; если имя равно коду — переводить нечего.
        if not model or not marketing or marketing.lower() == model.lower():
            continue
        if not any(ch.isdigit() for ch in model):
            continue
        full = marketing if not brand or marketing.lower().startswith(brand.lower()) else f'{brand} {marketing}'
        names.setdefault(model.lower(), collections.Counter())[full] += 1
    return {model: counter.most_common(1)[0][0] for model, counter in sorted(names.items())}


def encode_names(names: dict[str, str]) -> bytes:
    """Детерминированный gzip: одинаковые данные — байт-в-байт один файл."""
    payload = json.dumps(names, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
    return gzip.compress(payload, compresslevel=9, mtime=0)


def _read(path: Path) -> dict[str, str] | None:
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, ValueError, EOFError):
        return None
    return data if isinstance(data, dict) and data else None


def _names() -> dict[str, str]:
    # Справочник декоративный: без него кабинет просто покажет код модели.
    try:
        stat = REFRESHED_PATH.stat()
        key: tuple | None = (str(REFRESHED_PATH), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None
    if _cache['key'] == key and _cache['names']:
        return _cache['names']  # type: ignore[return-value]
    names = (_read(REFRESHED_PATH) if key else None) or _read(BUNDLED_PATH) or {}
    _cache['key'], _cache['names'] = key, names
    return names


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

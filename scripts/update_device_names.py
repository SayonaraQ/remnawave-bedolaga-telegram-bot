"""Обновить справочник «код модели Android → название» для кабинета.

Источник — список устройств, поддерживаемых Google Play:
https://storage.googleapis.com/play_public/supported_devices.csv (UTF-16).
Результат — `app/utils/device_names.json.gz`: ключ — код модели в нижнем
регистре, значение — название с брендом («POCO F8 Ultra», «Samsung Galaxy A55 5G»).

Запуск:  uv run python -m scripts.update_device_names [путь-к-csv]
Без аргумента скачивает свежий список. Повторный запуск на тех же данных даёт
байт-в-байт тот же файл (сортировка ключей, gzip без времени).
"""

from __future__ import annotations

import collections
import csv
import gzip
import io
import json
import sys
import urllib.request
from pathlib import Path


SOURCE_URL = 'https://storage.googleapis.com/play_public/supported_devices.csv'
OUTPUT = Path(__file__).resolve().parent.parent / 'app' / 'utils' / 'device_names.json.gz'


def read_rows(path: str | None) -> list[dict[str, str]]:
    raw = Path(path).read_bytes() if path else urllib.request.urlopen(SOURCE_URL, timeout=120).read()
    text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8')
    return list(csv.DictReader(io.StringIO(text)))


def build(rows: list[dict[str, str]]) -> dict[str, str]:
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


def main() -> None:
    mapping = build(read_rows(sys.argv[1] if len(sys.argv) > 1 else None))
    payload = json.dumps(mapping, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
    OUTPUT.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    print(f'{OUTPUT.relative_to(OUTPUT.parent.parent.parent)}: {len(mapping)} моделей, {OUTPUT.stat().st_size} байт')


if __name__ == '__main__':
    main()

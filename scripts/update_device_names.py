"""Пересобрать вшитый справочник «код модели Android → название».

Обычно не нужен: бот сам раз в месяц обновляет `data/device_names.json.gz`
(`app/services/device_names_refresh.py`). Этот скрипт обновляет запасной
справочник в репозитории — `app/utils/device_names.json.gz`, который попадает
в образ и работает, пока свежего файла в data ещё нет.

Источник — список устройств, поддерживаемых Google Play:
https://storage.googleapis.com/play_public/supported_devices.csv (UTF-16).

Запуск:  uv run python -m scripts.update_device_names [путь-к-csv]
Без аргумента скачивает свежий список. Повторный запуск на тех же данных даёт
байт-в-байт тот же файл.
"""

from __future__ import annotations

import importlib.util
import sys
import urllib.request
from pathlib import Path


SOURCE_URL = 'https://storage.googleapis.com/play_public/supported_devices.csv'
MODULE_PATH = Path(__file__).resolve().parent.parent / 'app' / 'utils' / 'device_names.py'


def _device_names_module():
    # Напрямую по пути: `import app.utils` тянет настройки бота, а без .env их нет.
    spec = importlib.util.spec_from_file_location('device_names', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    dn = _device_names_module()
    path = sys.argv[1] if len(sys.argv) > 1 else None
    raw = Path(path).read_bytes() if path else urllib.request.urlopen(SOURCE_URL, timeout=180).read()
    names = dn.build_names(dn.parse_csv(raw))
    dn.BUNDLED_PATH.write_bytes(dn.encode_names(names))
    print(f'{dn.BUNDLED_PATH.name}: {len(names)} моделей, {dn.BUNDLED_PATH.stat().st_size} байт')


if __name__ == '__main__':
    main()

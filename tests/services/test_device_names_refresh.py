"""Справочник названий устройств обновляется сам раз в месяц.

Новые телефоны («25102PCBEG» → «POCO F8 Ultra») появляются каждый месяц, а
вшитый в образ справочник стареет. Бот раз в сутки проверяет файл в
постоянной папке data/ и, если ему больше 30 дней, качает свежий список Google
Play. Плохая загрузка не должна затирать рабочий справочник.
"""

import gzip
import json
import os
import time
from pathlib import Path

import pytest

from app.services import device_names_refresh as refresh
from app.utils import device_names


CSV = (
    'Retail Branding,Marketing Name,Device,Model\n'
    '"POCO","POCO F9 Ultra","nova","26011PCBEG"\n'
    '"Samsung","Galaxy A57","a57","SM-A576E"\n'
).encode('utf-16')


def write_names(path: Path, mapping: dict[str, str], *, age_days: float = 0) -> None:
    path.write_bytes(gzip.compress(json.dumps(mapping).encode()))
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))


@pytest.fixture
def data_file(tmp_path, monkeypatch):
    path = tmp_path / 'device_names.json.gz'
    monkeypatch.setattr(device_names, 'REFRESHED_PATH', path)
    return path


@pytest.mark.asyncio
async def test_downloads_when_there_is_no_refreshed_file(data_file) -> None:
    async def fetch() -> bytes:
        return CSV

    assert await refresh.refresh_device_names(fetch=fetch, min_entries=1) == 'updated'
    assert device_names.marketing_name('Android', '26011PCBEG') == 'POCO F9 Ultra'
    assert device_names.marketing_name('Android', 'samsung SM-A576E') == 'Samsung Galaxy A57'


@pytest.mark.asyncio
async def test_leaves_a_fresh_file_alone(data_file) -> None:
    write_names(data_file, {'26011pcbeg': 'Old Name'}, age_days=3)

    async def fetch() -> bytes:
        raise AssertionError('свежий справочник не надо перекачивать')

    assert await refresh.refresh_device_names(fetch=fetch, min_entries=1) == 'fresh'
    assert device_names.marketing_name('Android', '26011PCBEG') == 'Old Name'


@pytest.mark.asyncio
async def test_replaces_a_month_old_file(data_file) -> None:
    write_names(data_file, {'26011pcbeg': 'Old Name'}, age_days=31)

    async def fetch() -> bytes:
        return CSV

    assert await refresh.refresh_device_names(fetch=fetch, min_entries=1) == 'updated'
    assert device_names.marketing_name('Android', '26011PCBEG') == 'POCO F9 Ultra'


@pytest.mark.asyncio
async def test_keeps_the_old_file_when_the_download_looks_truncated(data_file) -> None:
    write_names(data_file, {'26011pcbeg': 'Old Name'}, age_days=31)

    async def fetch() -> bytes:
        return CSV  # две модели при пороге в тысячу — обрезанная загрузка

    assert await refresh.refresh_device_names(fetch=fetch, min_entries=1000) == 'rejected'
    assert device_names.marketing_name('Android', '26011PCBEG') == 'Old Name'


@pytest.mark.asyncio
async def test_keeps_the_old_file_when_the_download_fails(data_file) -> None:
    write_names(data_file, {'26011pcbeg': 'Old Name'}, age_days=31)

    async def fetch() -> bytes:
        raise OSError('network is down')

    assert await refresh.refresh_device_names(fetch=fetch, min_entries=1) == 'failed'
    assert device_names.marketing_name('Android', '26011PCBEG') == 'Old Name'


def test_falls_back_to_the_bundled_names_when_the_file_is_broken(data_file) -> None:
    data_file.write_bytes(b'not a gzip')

    assert device_names.marketing_name('Android', '25102PCBEG') == 'POCO F8 Ultra'

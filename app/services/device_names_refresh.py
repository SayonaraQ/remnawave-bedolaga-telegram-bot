"""Ежемесячное обновление справочника названий устройств.

Новые телефоны выходят каждый месяц, а справочник, вшитый в образ
(`app/utils/device_names.json.gz`), стареет: в кабинете у них снова коды вроде
«25102PCBEG». Раз в сутки бот смотрит на `data/device_names.json.gz` и, если ему
больше 30 дней или его нет, качает свежий список Google Play и пересобирает файл.
Папка data переживает пересборку контейнера, кеш справочника подхватывает новый
файл сам — ни коммита, ни перевыкатки не нужно.

Плохая загрузка рабочий справочник не трогает: обрезанный список (меньше
`MIN_ENTRIES` моделей) и сетевые ошибки оставляют прежний файл, следующая
попытка — через сутки.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

import aiohttp
import structlog

from app.utils import device_names


logger = structlog.get_logger(__name__)

SOURCE_URL = 'https://storage.googleapis.com/play_public/supported_devices.csv'
MAX_AGE_SECONDS = 30 * 24 * 3600
CHECK_EVERY_SECONDS = 24 * 3600
FIRST_CHECK_DELAY_SECONDS = 5 * 60
# Полный список на 11.2026 — 23 тыс. моделей; заметно меньше значит обрезанную загрузку.
MIN_ENTRIES = 15_000


async def download_source() -> bytes:
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session, session.get(SOURCE_URL) as response:
        response.raise_for_status()
        return await response.read()


def _is_fresh(now: float) -> bool:
    try:
        return now - device_names.REFRESHED_PATH.stat().st_mtime < MAX_AGE_SECONDS
    except OSError:
        return False


async def refresh_device_names(
    fetch: Callable[[], Awaitable[bytes]] = download_source,
    *,
    min_entries: int = MIN_ENTRIES,
) -> str:
    """Обновить справочник, если устарел. Возвращает fresh / updated / rejected / failed."""
    if _is_fresh(time.time()):
        return 'fresh'
    try:
        names = device_names.build_names(device_names.parse_csv(await fetch()))
    except Exception as error:
        logger.warning('Не удалось скачать справочник названий устройств', error=str(error)[:200])
        return 'failed'
    if len(names) < min_entries:
        logger.warning('Справочник названий устройств подозрительно мал, оставляем прежний', entries=len(names))
        return 'rejected'
    path = device_names.REFRESHED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(device_names.encode_names(names))
    tmp.replace(path)
    logger.info('Справочник названий устройств обновлён', entries=len(names), path=str(path))
    return 'updated'


async def run_device_names_refresh() -> None:
    """Фоновая задача: первая проверка через 5 минут после старта, дальше раз в сутки."""
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            await refresh_device_names()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error('Ошибка обновления справочника названий устройств', error=str(error)[:200])
        await asyncio.sleep(CHECK_EVERY_SECONDS)

"""TV quick-connect helpers for Happ and v2raytun."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
import websockets
from websockets.exceptions import WebSocketException


HAPP_TV_API = 'https://check.happ.su/sendtv'
V2RAYTUN_STREAMVAULT_WS = 'wss://vault.v2raytunpulse.com'

_HAPP_CODE_RE = re.compile(r'^[A-Z0-9]{5}$', re.IGNORECASE)
_V2RAYTUN_KEY_RE = re.compile(r'^[0-9a-f]{32}$', re.IGNORECASE)


@dataclass(frozen=True)
class TvQuickConnectTarget:
    provider: str
    value: str


class TvQuickConnectSendError(RuntimeError):
    """Raised when a supported TV quick-connect provider rejects the request."""


def parse_tv_quick_connect_target(qr_data: str) -> TvQuickConnectTarget | None:
    """Parse QR payload from supported TV apps.

    Happ shows a 5-character code. v2raytun TV shows a 32-character
    StreamVault key in the QR code.
    """
    text = (qr_data or '').strip()
    if not text:
        return None

    happ_code = _extract_happ_code(text)
    if happ_code:
        return TvQuickConnectTarget(provider='happ', value=happ_code)

    v2raytun_key = _extract_v2raytun_key(text)
    if v2raytun_key:
        return TvQuickConnectTarget(provider='v2raytun', value=v2raytun_key)

    return None


async def send_tv_quick_connect_target(target: TvQuickConnectTarget, subscription_url: str) -> None:
    if target.provider == 'happ':
        await send_happ_tv_subscription(target.value, subscription_url)
        return

    if target.provider == 'v2raytun':
        await send_v2raytun_streamvault_subscription(target.value, subscription_url)
        return

    raise TvQuickConnectSendError(f'Unsupported TV provider: {target.provider}')


async def send_happ_tv_subscription(code: str, subscription_url: str) -> None:
    encoded_subscription = base64.b64encode(subscription_url.encode('utf-8')).decode('ascii')
    url = f'{HAPP_TV_API}/{code}'

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(url, json={'data': encoded_subscription})
    except httpx.HTTPError as exc:
        raise TvQuickConnectSendError('Happ TV request failed') from exc

    if not response.is_success:
        raise TvQuickConnectSendError(f'Happ TV returned HTTP {response.status_code}')


async def send_v2raytun_streamvault_subscription(
    key: str,
    subscription_url: str,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    request = {
        'action': 'PUT',
        'key': key.lower(),
        'value': subscription_url,
    }

    try:
        async with websockets.connect(
            V2RAYTUN_STREAMVAULT_WS,
            open_timeout=timeout_seconds,
            close_timeout=3,
        ) as websocket:
            await websocket.send(json.dumps(request, ensure_ascii=False, separators=(',', ':')))
            raw_response = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
    except (OSError, TimeoutError, WebSocketException) as exc:
        raise TvQuickConnectSendError('v2raytun StreamVault request failed') from exc

    if isinstance(raw_response, bytes):
        raw_response = raw_response.decode('utf-8', errors='replace')

    try:
        response: dict[str, Any] = json.loads(raw_response)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TvQuickConnectSendError('v2raytun StreamVault returned invalid response') from exc

    response_status = str(response.get('status', '')).upper()
    if response_status != 'SUCCESS':
        message = response.get('message') or 'v2raytun StreamVault rejected request'
        raise TvQuickConnectSendError(str(message))


def _extract_happ_code(text: str) -> str | None:
    if _HAPP_CODE_RE.fullmatch(text):
        return text.upper()

    url_candidates = _extract_url_candidates(text)
    for candidate in url_candidates:
        if _HAPP_CODE_RE.fullmatch(candidate):
            return candidate.upper()

    match = re.search(r'[/=]([A-Z0-9]{5})(?:[/?&\s]|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    return None


def _extract_v2raytun_key(text: str) -> str | None:
    if _V2RAYTUN_KEY_RE.fullmatch(text):
        return text.lower()

    for candidate in _extract_json_string_candidates(text):
        if _V2RAYTUN_KEY_RE.fullmatch(candidate):
            return candidate.lower()

    for candidate in _extract_url_candidates(text):
        if _V2RAYTUN_KEY_RE.fullmatch(candidate):
            return candidate.lower()

    return None


def _extract_json_string_candidates(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return []

    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            candidates.append(value.strip())
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return candidates


def _extract_url_candidates(text: str) -> list[str]:
    decoded_text = unquote(text.strip())
    try:
        parsed = urlparse(decoded_text)
    except ValueError:
        return []

    if not parsed.scheme:
        return []

    candidates: list[str] = []
    if parsed.netloc:
        candidates.append(unquote(parsed.netloc.strip('/')))

    path_parts = [unquote(part) for part in parsed.path.split('/') if part]
    candidates.extend(path_parts)

    query_values = []
    if parsed.query:
        for pair in parsed.query.split('&'):
            if '=' in pair:
                _, value = pair.split('=', 1)
                query_values.append(unquote(value))
    candidates.extend(query_values)

    return [candidate.strip() for candidate in candidates if candidate.strip()]

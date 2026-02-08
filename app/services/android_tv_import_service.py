import asyncio
import io
import json
import logging
import re
from urllib.parse import urlparse

from PIL import Image, ImageOps
import websockets

from app.config import settings


logger = logging.getLogger(__name__)

STREAMVAULT_KEY_PATTERN = re.compile(r'\b[a-fA-F0-9]{32}\b')


class AndroidTvImportError(RuntimeError):
    """Base error for Android TV import flow."""


class AndroidTvQrDecodeError(AndroidTvImportError):
    """Raised when QR code cannot be decoded from user photo."""


class AndroidTvStreamVaultError(AndroidTvImportError):
    """Raised when payload cannot be sent to StreamVault websocket."""


def extract_streamvault_key(raw_qr_data: str) -> str | None:
    payload = (raw_qr_data or '').strip()
    if not payload:
        return None

    exact_match = STREAMVAULT_KEY_PATTERN.fullmatch(payload)
    if exact_match:
        return exact_match.group(0).lower()

    try:
        parsed_payload = json.loads(payload)
    except Exception:
        parsed_payload = None

    if isinstance(parsed_payload, dict):
        for value in parsed_payload.values():
            if not isinstance(value, str):
                continue
            nested_match = STREAMVAULT_KEY_PATTERN.search(value)
            if nested_match:
                return nested_match.group(0).lower()

    match = STREAMVAULT_KEY_PATTERN.search(payload)
    if match:
        return match.group(0).lower()

    return None


def build_streamvault_put_message(key: str, value: str) -> str:
    payload = {
        'action': 'PUT',
        'data': json.dumps({'key': key, 'value': value}, separators=(',', ':')),
    }
    return json.dumps(payload, separators=(',', ':'))


def _derive_origin_from_ws_url(ws_url: str) -> str | None:
    parsed = urlparse(ws_url)
    if parsed.scheme not in {'ws', 'wss'} or not parsed.netloc:
        return None

    http_scheme = 'https' if parsed.scheme == 'wss' else 'http'
    return f'{http_scheme}://{parsed.netloc}'


def _decode_qr_payloads(image: Image.Image) -> list[str]:
    try:
        from pyzbar.pyzbar import decode as decode_qr
    except Exception as exc:
        raise AndroidTvQrDecodeError('QR decoder dependency is not available on this server') from exc

    payloads: list[str] = []
    for decoded in decode_qr(image):
        raw_value = decoded.data
        if not raw_value:
            continue

        try:
            text_value = raw_value.decode('utf-8').strip()
        except Exception:
            text_value = raw_value.decode('utf-8', errors='ignore').strip()

        if text_value:
            payloads.append(text_value)

    return payloads


def decode_android_tv_qr_key(image_bytes: bytes) -> str:
    if not image_bytes:
        raise AndroidTvQrDecodeError('Empty image payload')

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            normalized = ImageOps.exif_transpose(image).convert('RGB')
    except Exception as exc:
        raise AndroidTvQrDecodeError('Cannot open image data') from exc

    grayscale = ImageOps.grayscale(normalized)
    candidates = [
        normalized,
        grayscale,
        ImageOps.autocontrast(grayscale),
    ]

    for candidate in candidates:
        for qr_payload in _decode_qr_payloads(candidate):
            key = extract_streamvault_key(qr_payload)
            if key:
                return key

    raise AndroidTvQrDecodeError('QR key was not found in image')


async def publish_streamvault_subscription(key: str, subscription_url: str) -> str | None:
    ws_url = settings.ANDROID_TV_STREAMVAULT_WS_URL.strip()
    if not ws_url:
        raise AndroidTvStreamVaultError('ANDROID_TV_STREAMVAULT_WS_URL is empty')

    origin = settings.ANDROID_TV_STREAMVAULT_ORIGIN.strip() or _derive_origin_from_ws_url(ws_url)
    timeout_seconds = max(1, int(settings.ANDROID_TV_STREAMVAULT_TIMEOUT_SECONDS))
    user_agent = settings.ANDROID_TV_STREAMVAULT_USER_AGENT.strip() or 'okhttp/3.10.0'
    message = build_streamvault_put_message(key, subscription_url)

    connect_kwargs = {'compression': None}
    if origin:
        connect_kwargs['origin'] = origin

    try:
        connection = websockets.connect(
            ws_url,
            additional_headers=[('User-Agent', user_agent)],
            **connect_kwargs,
        )
    except TypeError:
        connection = websockets.connect(
            ws_url,
            extra_headers=[('User-Agent', user_agent)],
            **connect_kwargs,
        )

    try:
        async with asyncio.timeout(timeout_seconds):
            async with connection as websocket:
                await websocket.send(message)
                response = await websocket.recv()
                return response if isinstance(response, str) else str(response)
    except TimeoutError as exc:
        raise AndroidTvStreamVaultError('Timeout while sending websocket payload') from exc
    except Exception as exc:
        raise AndroidTvStreamVaultError(f'Websocket request failed: {exc}') from exc

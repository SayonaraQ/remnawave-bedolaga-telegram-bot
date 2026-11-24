"""Expose attachment indexes for ticket albums and legacy single files.

The media endpoint serves client messages so the assistant can inspect screenshots
while staff uploads stay private. It checks file signatures because filenames and
Telegram metadata do not establish that an attachment is an image.
"""

from __future__ import annotations

import asyncio
import hmac
from ipaddress import ip_address, ip_network

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot_factory import create_bot
from app.config import settings
from app.database.crud.ticket import TicketCRUD
from app.database.crud.user import get_user_by_telegram_id
from app.database.models import Subscription, Ticket, User
from app.utils.ticket_media import get_ticket_media

from ..dependencies import get_db_session
from ..schemas.support import (
    SupportAttachment,
    SupportCard,
    SupportPriorityRequest,
    SupportReplyRequest,
    SupportReplyResponse,
    SupportStatusRequest,
    SupportSubscription,
    SupportTicket,
    SupportTicketDetail,
    SupportTicketMessage,
    SupportTicketStatus,
)
from ..schemas.tickets import TicketPriorityUpdateRequest, TicketReplyRequest, TicketStatusUpdateRequest
from . import tickets


router = APIRouter()
logger = structlog.get_logger(__name__)

SUPPORT_MEDIA_MAX_BYTES = 5_000_000


def _is_allowed_client(host: str) -> bool:
    try:
        address = ip_address(host)
    except ValueError:
        return False

    for entry in settings.SUPPORT_API_ALLOWED_IPS.split(','):
        try:
            network = ip_network(entry.strip(), strict=False)
        except ValueError:
            continue
        if address in network:
            return True

    return False


async def require_support_token(request: Request) -> None:
    expected_token = settings.SUPPORT_API_TOKEN
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Support API is disabled')

    if request.client is None or not _is_allowed_client(request.client.host):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Client IP is not allowed')

    scheme, credentials = get_authorization_scheme_param(request.headers.get('Authorization'))
    token = credentials if scheme.lower() == 'bearer' and credentials else request.headers.get('X-Support-Token')
    if not token or not hmac.compare_digest(token.encode(), expected_token.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or missing support token')


async def _load_user(db: AsyncSession, telegram_id: int) -> User | None:
    return await get_user_by_telegram_id(db, telegram_id)


async def _load_subscriptions(db: AsyncSession, user_id: int) -> list[Subscription]:
    result = await db.scalars(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .options(selectinload(Subscription.tariff))
        .order_by(Subscription.id)
    )
    return list(result.all())


async def _has_open_ticket(db: AsyncSession, user_id: int) -> bool:
    # open or answered: the same «active ticket» rule the bot itself uses
    return await TicketCRUD.user_has_active_ticket(db, user_id)


@router.get('/card/{telegram_id}', response_model=SupportCard, dependencies=[Depends(require_support_token)])
async def get_support_card(telegram_id: int, db: AsyncSession = Depends(get_db_session)) -> SupportCard:
    user = await _load_user(db, telegram_id)
    if user is None:
        return SupportCard(
            telegram_id=telegram_id,
            registered=False,
            balance_kopeks=None,
            email_bound=False,
            language=None,
            has_open_ticket=False,
            subscriptions=[],
            connect_urls={},
        )

    subscriptions = await _load_subscriptions(db, user.id)
    return SupportCard(
        telegram_id=telegram_id,
        registered=True,
        balance_kopeks=user.balance_kopeks,
        email_bound=bool(user.email),
        language=user.language,
        has_open_ticket=await _has_open_ticket(db, user.id),
        subscriptions=[
            SupportSubscription(
                id=sub.id,
                status=sub.status,
                is_trial=bool(sub.is_trial),
                end_date=sub.end_date,
                tariff_name=sub.tariff.name if sub.tariff else None,
                traffic_limit_gb=sub.traffic_limit_gb,
                traffic_used_gb=sub.traffic_used_gb,
                purchased_traffic_gb=sub.purchased_traffic_gb,
                traffic_reset_at=sub.traffic_reset_at,
                traffic_accounting_mode=sub.traffic_accounting_mode,
                device_limit=sub.device_limit,
                autopay_enabled=bool(sub.autopay_enabled),
                # per-row flag kept by the grace store in the same transaction; correct in every grace mode
                grace_open=bool(getattr(sub, 'grace_session_open', False)),
                panel_user_id=sub.remnawave_id,
            )
            for sub in subscriptions
        ],
        connect_urls={sub.id: sub.subscription_url for sub in subscriptions if sub.subscription_url},
    )


async def _load_tickets(db: AsyncSession, status: str | None, limit: int) -> list[Ticket]:
    ticket_list = await TicketCRUD.get_all_tickets(db, status=status, limit=limit, offset=0)
    if ticket_list:
        # Populate messages on the ticket instances already loaded with their users.
        await db.execute(
            select(Ticket)
            .where(Ticket.id.in_([ticket.id for ticket in ticket_list]))
            .options(selectinload(Ticket.messages))
        )
    return ticket_list


async def _load_ticket(db: AsyncSession, ticket_id: int) -> Ticket | None:
    return await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=True, load_user=True)


def _serialize_ticket(ticket: Ticket) -> SupportTicket:
    last_message = max(ticket.messages, key=lambda message: message.id, default=None)
    return SupportTicket(
        id=ticket.id,
        user_telegram_id=ticket.user.telegram_id if ticket.user is not None else None,
        status=ticket.status,
        priority=ticket.priority,
        title=ticket.title,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        last_message_id=last_message.id if last_message is not None else None,
        last_message_from_admin=last_message.is_from_admin if last_message is not None else None,
    )


@router.get('/tickets', response_model=list[SupportTicket], dependencies=[Depends(require_support_token)])
async def list_support_tickets(
    status_filter: SupportTicketStatus = Query('open', alias='status'),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> list[SupportTicket]:
    return [_serialize_ticket(ticket) for ticket in await _load_tickets(db, status=status_filter, limit=limit)]


@router.get('/tickets/{ticket_id}', response_model=SupportTicketDetail, dependencies=[Depends(require_support_token)])
async def get_support_ticket(ticket_id: int, db: AsyncSession = Depends(get_db_session)) -> SupportTicketDetail:
    ticket = await _load_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Ticket not found')

    return SupportTicketDetail(
        **_serialize_ticket(ticket).model_dump(),
        messages=[
            SupportTicketMessage(
                id=message.id,
                is_from_admin=message.is_from_admin,
                text=message.message_text,
                # albums keep their files in media_items and may leave has_media unset
                has_media=bool(message.has_media) or bool(getattr(message, 'media_items', None)),
                created_at=message.created_at,
                attachments=[
                    SupportAttachment(index=index, type=item['type'])
                    for index, item in enumerate(get_ticket_media(message))
                ],
            )
            for message in sorted(ticket.messages, key=lambda message: message.id)
        ],
    )


def _support_image_type(data: bytes) -> str | None:
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


@router.get('/tickets/{ticket_id}/messages/{message_id}/media/{index}', dependencies=[Depends(require_support_token)])
async def get_support_ticket_media(
    ticket_id: int, message_id: int, index: int, db: AsyncSession = Depends(get_db_session)
) -> Response:
    ticket = await _load_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Ticket not found')

    message = next((message for message in ticket.messages if message.id == message_id), None)
    if message is None or message.is_from_admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Message not found')

    attachments = get_ticket_media(message)
    if not 0 <= index < len(attachments):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Attachment not found')
    item = attachments[index]
    if item['type'] == 'video':
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 'Unsupported attachment type')

    try:
        bot = create_bot()
        try:
            file = await bot.get_file(item['file_id'])
            if file.file_size is not None and file.file_size > SUPPORT_MEDIA_MAX_BYTES:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, 'Attachment is too large')
            if not file.file_path:
                raise ValueError('Telegram did not return a file path')
            async with asyncio.timeout(20):
                buffer = await bot.download_file(file.file_path)
            if buffer is None:
                raise ValueError('Telegram did not return a download buffer')
            data = buffer.read(SUPPORT_MEDIA_MAX_BYTES + 1)
        finally:
            await bot.session.close()
    except HTTPException:
        raise
    except Exception as error:
        logger.warning(
            'Failed to download ticket media',
            ticket_id=ticket_id,
            message_id=message_id,
            index=index,
            error_type=type(error).__name__,
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, 'Failed to download ticket media') from None

    if len(data) > SUPPORT_MEDIA_MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, 'Attachment is too large')
    media_type = _support_image_type(data)
    if media_type is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 'Unsupported attachment type')

    return Response(
        content=data,
        media_type=media_type,
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
    )


@router.post(
    '/tickets/{ticket_id}/reply', response_model=SupportReplyResponse, dependencies=[Depends(require_support_token)]
)
async def reply_to_support_ticket(
    ticket_id: int, body: SupportReplyRequest, db: AsyncSession = Depends(get_db_session)
) -> SupportReplyResponse:
    result = await tickets.reply_to_ticket(
        ticket_id=ticket_id, payload=TicketReplyRequest(message_text=body.text), _=None, db=db
    )
    return SupportReplyResponse(message_id=result.message.id)


@router.post('/tickets/{ticket_id}/status', dependencies=[Depends(require_support_token)])
async def update_support_ticket_status(
    ticket_id: int, body: SupportStatusRequest, db: AsyncSession = Depends(get_db_session)
) -> dict[str, bool]:
    await tickets.update_ticket_status(
        ticket_id=ticket_id, payload=TicketStatusUpdateRequest(status=body.status), _=None, db=db
    )
    return {'ok': True}


@router.post('/tickets/{ticket_id}/priority', dependencies=[Depends(require_support_token)])
async def update_support_ticket_priority(
    ticket_id: int, body: SupportPriorityRequest, db: AsyncSession = Depends(get_db_session)
) -> dict[str, bool]:
    await tickets.update_ticket_priority(
        ticket_id=ticket_id, payload=TicketPriorityUpdateRequest(priority=body.priority), _=None, db=db
    )
    return {'ok': True}

from __future__ import annotations

import hmac
from ipaddress import ip_address, ip_network

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.crud.ticket import TicketCRUD
from app.database.crud.user import get_user_by_telegram_id
from app.database.models import Subscription, User
from app.services.grace_access_runtime import get_open_grace_subscription_ids

from ..dependencies import get_db_session
from ..schemas.support import SupportCard, SupportSubscription


router = APIRouter()


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


async def _open_grace_ids(db: AsyncSession) -> set[int]:
    return await get_open_grace_subscription_ids(db)


async def _has_open_ticket(db: AsyncSession, user_id: int) -> bool:
    return bool(await TicketCRUD.get_user_tickets(db, user_id=user_id, status='open', limit=1))


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
    grace_ids = await _open_grace_ids(db)
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
                grace_open=sub.id in grace_ids,
                panel_user_id=sub.remnawave_id,
            )
            for sub in subscriptions
        ],
        connect_urls={sub.id: sub.subscription_url for sub in subscriptions if sub.subscription_url},
    )

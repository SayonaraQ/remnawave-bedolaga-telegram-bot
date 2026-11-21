from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SupportSubscription(BaseModel):
    id: int
    status: str
    is_trial: bool
    end_date: datetime | None
    tariff_name: str | None
    traffic_limit_gb: int | None
    traffic_used_gb: float | None
    purchased_traffic_gb: int | None
    traffic_reset_at: datetime | None
    traffic_accounting_mode: str | None
    device_limit: int | None
    autopay_enabled: bool
    grace_open: bool
    panel_user_id: int | None


class SupportCard(BaseModel):
    telegram_id: int
    registered: bool
    balance_kopeks: int | None
    email_bound: bool
    language: str | None
    has_open_ticket: bool
    subscriptions: list[SupportSubscription]
    connect_urls: dict[int, str]


SupportTicketStatus = Literal['open', 'answered', 'closed', 'pending']


class SupportTicket(BaseModel):
    id: int
    user_telegram_id: int | None
    status: str
    priority: str
    title: str
    created_at: datetime | None
    updated_at: datetime | None
    last_message_id: int | None
    last_message_from_admin: bool | None


class SupportTicketMessage(BaseModel):
    id: int
    is_from_admin: bool
    text: str
    has_media: bool
    created_at: datetime | None


class SupportTicketDetail(SupportTicket):
    messages: list[SupportTicketMessage]


class SupportReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SupportReplyResponse(BaseModel):
    message_id: int


class SupportStatusRequest(BaseModel):
    status: SupportTicketStatus


class SupportPriorityRequest(BaseModel):
    priority: Literal['low', 'normal', 'high', 'urgent']

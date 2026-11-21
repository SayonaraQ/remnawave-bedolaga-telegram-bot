from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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

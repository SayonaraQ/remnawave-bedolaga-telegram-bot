"""Enabled theme preferences and animated background validation."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.cabinet.routes import branding as branding_routes


@pytest.mark.parametrize(
    ('stored', 'expected'),
    [
        (None, {'dark': True, 'light': True, 'seasonal': False, 'seasonalAdminsOnly': False, 'seasonalDefault': True}),
        (
            '{"dark": true, "light": false}',
            {'dark': True, 'light': False, 'seasonal': False, 'seasonalAdminsOnly': False, 'seasonalDefault': True},
        ),
        (
            '{"dark": false, "light": true, "seasonal": true, "seasonalAdminsOnly": false, "seasonalDefault": false}',
            {'dark': False, 'light': True, 'seasonal': True, 'seasonalAdminsOnly': False, 'seasonalDefault': False},
        ),
        (
            'not json',
            {'dark': True, 'light': True, 'seasonal': False, 'seasonalAdminsOnly': False, 'seasonalDefault': True},
        ),
    ],
)
async def test_get_enabled_themes_uses_defaults_for_missing_settings(stored: str | None, expected: dict) -> None:
    with patch('app.cabinet.routes.branding.get_setting_value', AsyncMock(return_value=stored)):
        response = await branding_routes.get_enabled_themes(db=AsyncMock())

    assert response.model_dump() == expected


@pytest.mark.parametrize(
    ('update', 'expected_seasonal'),
    [
        ({'seasonal': True}, {'seasonal': True, 'seasonalAdminsOnly': False, 'seasonalDefault': True}),
        ({'seasonalDefault': False}, {'seasonal': False, 'seasonalAdminsOnly': False, 'seasonalDefault': False}),
        ({'seasonalAdminsOnly': True}, {'seasonal': False, 'seasonalAdminsOnly': True, 'seasonalDefault': True}),
    ],
)
async def test_patch_seasonal_flags_preserves_legacy_themes(update: dict, expected_seasonal: dict) -> None:
    db = AsyncMock()
    stored = '{"dark": true, "light": false}'
    with (
        patch('app.cabinet.routes.branding.get_setting_value', AsyncMock(return_value=stored)),
        patch('app.cabinet.routes.branding.set_setting_value', new_callable=AsyncMock) as save,
    ):
        response = await branding_routes.update_enabled_themes(
            payload=branding_routes.EnabledThemesUpdate(**update),
            admin=SimpleNamespace(telegram_id=123),
            db=db,
        )

    expected = {'dark': True, 'light': False, **expected_seasonal}
    assert response.model_dump() == expected
    save.assert_awaited_once_with(db, branding_routes.ENABLED_THEMES_KEY, json.dumps(expected))


async def test_patch_null_flags_preserves_stored_preferences() -> None:
    stored = {'dark': False, 'light': True, 'seasonal': True, 'seasonalAdminsOnly': False, 'seasonalDefault': False}
    with (
        patch('app.cabinet.routes.branding.get_setting_value', AsyncMock(return_value=json.dumps(stored))),
        patch('app.cabinet.routes.branding.set_setting_value', new_callable=AsyncMock) as save,
    ):
        response = await branding_routes.update_enabled_themes(
            payload=branding_routes.EnabledThemesUpdate(
                dark=None, light=None, seasonal=None, seasonalAdminsOnly=None, seasonalDefault=None
            ),
            admin=SimpleNamespace(telegram_id=123),
            db=AsyncMock(),
        )

    assert response.model_dump() == stored
    assert json.loads(save.await_args.args[2]) == stored


async def test_patch_cannot_disable_both_core_themes_even_with_seasonal_enabled() -> None:
    with (
        patch('app.cabinet.routes.branding.get_setting_value', AsyncMock(return_value=None)),
        patch('app.cabinet.routes.branding.set_setting_value', new_callable=AsyncMock) as save,
        pytest.raises(HTTPException) as exc,
    ):
        await branding_routes.update_enabled_themes(
            payload=branding_routes.EnabledThemesUpdate(dark=False, light=False, seasonal=True),
            admin=SimpleNamespace(telegram_id=123),
            db=AsyncMock(),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == 'At least one theme must be enabled'
    save.assert_not_awaited()


def test_animation_config_accepts_liquid_light() -> None:
    config = branding_routes.AnimationConfigUpdate(type='liquid-light')

    assert config.type == 'liquid-light'
    assert 'liquid-light' in branding_routes.ALLOWED_BG_TYPES


def test_animation_config_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError, match='type'):
        branding_routes.AnimationConfigUpdate(type='unknown-background')

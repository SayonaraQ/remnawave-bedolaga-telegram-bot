"""Фон для светлой темы: отдельный эффект поверх общего конфига анимации."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import get_args
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.cabinet.routes import branding as branding_routes


STORED = {
    'enabled': True,
    'type': 'stardust',
    'settings': {},
    'opacity': 1.0,
    'blur': 0,
    'reducedOnMobile': True,
}


def test_background_types_have_one_source_of_truth() -> None:
    assert get_args(branding_routes.BackgroundType) == branding_routes.ALLOWED_BG_TYPES
    assert {'liquid-light', 'halo', 'stardust', 'none'} <= set(branding_routes.ALLOWED_BG_TYPES)


def test_config_without_light_inherits() -> None:
    response = branding_routes.AnimationConfigResponse(**STORED)

    assert response.light.inherit is True


def test_update_accepts_partial_light() -> None:
    update = branding_routes.AnimationConfigUpdate(light={'type': 'halo'})

    assert update.model_dump(exclude_none=True) == {'light': {'type': 'halo'}}


@pytest.mark.parametrize(
    'light',
    [
        {'type': 'unknown-background'},
        {'settings': {'nested': {'x': 1}}},
        {'opacity': 1.5},
        {'blur': 101},
    ],
)
def test_update_rejects_invalid_light(light: dict) -> None:
    with pytest.raises(ValidationError):
        branding_routes.AnimationConfigUpdate(light=light)


def test_merge_keeps_light_fields_across_partial_updates() -> None:
    merged = branding_routes._merge_animation_config(STORED, {'light': {'inherit': False}})
    merged = branding_routes._merge_animation_config(merged, {'light': {'type': 'halo'}})

    assert merged['light'] == {'inherit': False, 'type': 'halo'}
    assert merged['type'] == 'stardust'


def test_merge_without_light_leaves_it_untouched() -> None:
    current = {**STORED, 'light': {'inherit': False, 'type': 'halo', 'opacity': 0.8}}

    merged = branding_routes._merge_animation_config(current, {'opacity': 0.5})

    assert merged['opacity'] == 0.5
    assert merged['light'] == {'inherit': False, 'type': 'halo', 'opacity': 0.8}


def test_merge_replaces_garbage_light() -> None:
    merged = branding_routes._merge_animation_config({**STORED, 'light': 'x'}, {'light': {'inherit': False}})

    assert merged['light'] == {'inherit': False}


async def test_get_with_garbage_light_returns_main_config() -> None:
    stored = json.dumps({**STORED, 'light': 'x'})
    with patch('app.cabinet.routes.branding.get_setting_value', AsyncMock(return_value=stored)):
        response = await branding_routes.get_animation_config(db=AsyncMock())

    assert response.type == 'stardust'
    assert response.light.inherit is True


async def test_patch_light_is_saved_and_returned() -> None:
    stored = json.dumps({**STORED, 'light': {'inherit': False, 'type': 'liquid-light'}})
    with (
        patch('app.cabinet.routes.branding.get_setting_value', AsyncMock(return_value=stored)),
        patch('app.cabinet.routes.branding.set_setting_value', new_callable=AsyncMock) as save,
    ):
        response = await branding_routes.update_animation_config(
            payload=branding_routes.AnimationConfigUpdate(light={'type': 'halo', 'opacity': 0.7}),
            admin=SimpleNamespace(telegram_id=123),
            db=AsyncMock(),
        )

    assert response.type == 'stardust'
    assert response.light.model_dump() == {
        'inherit': False,
        'type': 'halo',
        'settings': {},
        'opacity': 0.7,
        'blur': 0,
    }
    saved = json.loads(save.await_args_list[0].args[2])
    assert saved['light'] == {'inherit': False, 'type': 'halo', 'opacity': 0.7}

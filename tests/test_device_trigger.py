from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
)

from custom_components.pixels_dice import device_trigger
from custom_components.pixels_dice.const import DOMAIN


@pytest.mark.asyncio
async def test_async_get_triggers(hass):
    """Device triggers are created for face and state sensors."""
    entries = [
        SimpleNamespace(domain="sensor", platform=DOMAIN, unique_id="die_face", entity_id="sensor.die_face"),
        SimpleNamespace(domain="sensor", platform=DOMAIN, unique_id="die_state", entity_id="sensor.die_state"),
    ]

    with patch("custom_components.pixels_dice.device_trigger.er.async_get"), patch(
        "custom_components.pixels_dice.device_trigger.er.async_entries_for_device",
        return_value=entries,
    ):
        triggers = await device_trigger.async_get_triggers(hass, "device123")

    assert triggers == [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: "device123",
            CONF_ENTITY_ID: "sensor.die_face",
            "type": "face",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: "device123",
            CONF_ENTITY_ID: "sensor.die_state",
            "type": "state",
        },
    ]


@pytest.mark.asyncio
async def test_async_attach_trigger_calls_action(hass):
    """The trigger fires when state transitions match."""
    callbacks = []

    def fake_track(hass, entity_ids, callback):
        callbacks.append(callback)
        return lambda: None

    action = AsyncMock()

    with patch(
        "custom_components.pixels_dice.device_trigger.async_track_state_change_event",
        side_effect=fake_track,
    ):
        await device_trigger.async_attach_trigger(
            hass,
            {
                CONF_ENTITY_ID: "sensor.die_state",
                device_trigger.CONF_FROM: "Rolling",
                device_trigger.CONF_TO: "Landed",
            },
            action,
            {},
        )

    event = SimpleNamespace(
        data={
            "old_state": SimpleNamespace(state="Rolling"),
            "new_state": SimpleNamespace(state="Landed"),
        }
    )
    await callbacks[0](event)

    action.assert_awaited_once()

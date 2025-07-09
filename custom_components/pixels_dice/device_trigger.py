"""Device triggers for Pixels Dice sensors."""
from __future__ import annotations

from typing import Any, Callable, Final

import voluptuous as vol
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
)

CONF_FROM = "from"
CONF_TO = "to"
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN

TRIGGER_TYPES: Final = {"face", "state"}

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required("type"): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_ENTITY_ID): str,
        vol.Optional(CONF_FROM): str,
        vol.Optional(CONF_TO): str,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return a list of triggers for the device."""
    triggers: list[dict[str, Any]] = []
    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_device(ent_reg, device_id, True):
        if entry.domain != "sensor" or entry.platform != DOMAIN:
            continue
        if entry.unique_id.endswith("_face"):
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_ENTITY_ID: entry.entity_id,
                    "type": "face",
                }
            )
        elif entry.unique_id.endswith("_state"):
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_ENTITY_ID: entry.entity_id,
                    "type": "state",
                }
            )
    return triggers


def async_get_trigger_capabilities(hass: HomeAssistant, trigger: dict[str, Any]) -> vol.Schema:
    """Return the capabilities for a device trigger."""
    return vol.Schema({vol.Optional(CONF_FROM): str, vol.Optional(CONF_TO): str})


async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict[str, Any],
    action: Callable[..., Any],
    automation_info: dict[str, Any],
) -> Callable[[], None]:
    """Attach a trigger."""
    entity_id = config[CONF_ENTITY_ID]
    to_state = config.get(CONF_TO)
    from_state = config.get(CONF_FROM)

    async def state_changed(event):
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if from_state is not None and (old is None or old.state != from_state):
            return
        if to_state is not None and (new is None or new.state != to_state):
            return
        await action({})

    return async_track_state_change_event(hass, [entity_id], state_changed)

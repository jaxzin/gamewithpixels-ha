import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .sensor import PixelsDiceEntity, PixelsDiceDevice

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Pixels Dice switches."""
    pixels_device = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([PixelsDiceAutoconnectSwitch(pixels_device)])


class PixelsDiceAutoconnectSwitch(PixelsDiceEntity, SwitchEntity):
    """Representation of a Pixels Dice autoconnect switch."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def device_info(self):
        """Return the device info."""
        return self._pixels_device.device_info

    def __init__(self, pixels_device) -> None:
        """Initialize the switch."""
        self._pixels_device = pixels_device
        self._attr_name = f"{self._pixels_device.die_name} Autoconnect"
        self._attr_unique_id = f"{self._pixels_device.unique_id}_autoconnect"
        self._attr_is_on = self._pixels_device.autoconnect

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._pixels_device.autoconnect

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._pixels_device.autoconnect = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._pixels_device.autoconnect = False
        self._attr_is_on = False
        self.async_write_ha_state()

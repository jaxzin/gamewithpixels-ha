import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sensor import PixelsDiceDevice, PixelsDiceEntity  # Import base classes

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Pixels Dice button platform."""
    _LOGGER.debug("Setting up Pixels Dice button platform from config entry")
    unique_id = config_entry.unique_id
    pixels_device = hass.data[DOMAIN][unique_id] # Retrieve the shared device instance

    async_add_entities([
        PixelsDiceConnectButton(pixels_device),
        PixelsDiceDisconnectButton(pixels_device),
    ])


class PixelsDiceConnectButton(PixelsDiceEntity, ButtonEntity):
    """Representation of the Pixels Dice connect button."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} Connect"
        self._attr_unique_id = f"{pixels_device.unique_id}_connect_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._pixels_device.async_connect_die()


class PixelsDiceDisconnectButton(PixelsDiceEntity, ButtonEntity):
    """Representation of the Pixels Dice disconnect button."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} Disconnect"
        self._attr_unique_id = f"{pixels_device.unique_id}_disconnect_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._pixels_device.async_disconnect_die()

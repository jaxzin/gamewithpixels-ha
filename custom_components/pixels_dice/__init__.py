"""The Pixels Dice integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sensor import PixelsDiceDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pixels Dice from a config entry."""
    _LOGGER.debug("Setting up Pixels Dice integration")

    hass.data.setdefault(DOMAIN, {})

    pixels_device = PixelsDiceDevice(
        hass,
        entry.data["name"],
        entry.unique_id,
        entry.data.get("autoconnect", False),
    )
    hass.data[DOMAIN][entry.unique_id] = pixels_device

    await pixels_device.async_added_to_hass()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Pixels Dice integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        pixels_device = hass.data[DOMAIN].get(entry.unique_id)
        if pixels_device:
            await pixels_device.async_will_remove_from_hass()
            hass.data[DOMAIN].pop(entry.unique_id, None)

    return unload_ok


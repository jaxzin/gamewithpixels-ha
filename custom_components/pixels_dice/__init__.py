"""The Pixels Dice integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pixels_dice"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pixels Dice from a config entry."""
    _LOGGER.debug("Setting up Pixels Dice integration")
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, entry.data, entry)
    )

    async def handle_connect(call):
        entity_id = call.data.get("entity_id")
        if entity_id:
            # Extract unique_id from entity_id (e.g., sensor.pixels_dice_brian_pd6 -> pixels_dice_brian_pd6)
            unique_id = entity_id.split('.')[-1]
            sensor_entity = hass.data[DOMAIN].get(unique_id)
            if sensor_entity:
                await sensor_entity.async_connect_die()
            else:
                _LOGGER.warning(f"Could not find sensor entity for {entity_id} (unique_id: {unique_id})")
        else:
            _LOGGER.error("No entity_id provided for connect service.")

    async def handle_disconnect(call):
        entity_id = call.data.get("entity_id")
        if entity_id:
            unique_id = entity_id.split('.')[-1]
            sensor_entity = hass.data[DOMAIN].get(unique_id)
            if sensor_entity:
                await sensor_entity.async_disconnect_die()
            else:
                _LOGGER.warning(f"Could not find sensor entity for {entity_id} (unique_id: {unique_id})")
        else:
            _LOGGER.error("No entity_id provided for disconnect service.")

    hass.services.async_register(DOMAIN, "connect", handle_connect)
    hass.services.async_register(DOMAIN, "disconnect", handle_disconnect)

    hass.data.setdefault(DOMAIN, {})

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Pixels Dice integration")
    # TODO: Implement actual unload logic here
    return True

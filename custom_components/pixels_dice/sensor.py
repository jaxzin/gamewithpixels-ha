
import asyncio
import logging

from bleak import BleakScanner, BleakClient
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The specific Bluetooth service and characteristic UUIDs for Pixels dice.
PIXEL_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
PIXEL_NOTIFY_CHAR_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Pixels Dice sensor platform."""
    _LOGGER.debug("Setting up Pixels Dice sensor platform from config entry")
    die_name = config_entry.data["name"]
    sensor = PixelsDiceSensor(die_name)
    async_add_entities([sensor])

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


class PixelsDiceSensor(SensorEntity):
    """Representation of a Pixels Dice sensor."""

    def __init__(self, die_name: str) -> None:
        """Initialize the sensor."""
        self._die_name = die_name
        self._state = None
        self._address = None
        self._client = None
        self._attr_name = f"Pixels Dice {die_name}"
        self._attr_unique_id = f"pixels_dice_{die_name.lower().replace(' ', '_')}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to Home Assistant."""
        _LOGGER.debug(f"Pixels Dice sensor {self.name} added to Home Assistant")
        self.hass.data.setdefault(DOMAIN, {})[self.unique_id] = self

    async def async_will_remove_from_hass(self) -> None:
        """Run when this entity is being removed from Home Assistant."""
        _LOGGER.debug(f"Pixels Dice sensor {self.name} will be removed from Home Assistant")
        await self.async_disconnect_die()

    async def async_connect_die(self):
        """Connect to the Pixels die and start listening for notifications."""
        _LOGGER.info(f"Scanning for a Pixels die named '{self._die_name}'...")
        device = await BleakScanner.find_device_by_name(self._die_name)

        if device is None:
            _LOGGER.warning(f"Could not find a die named '{self._die_name}'. Make sure it's on and nearby.")
            return

        _LOGGER.info(f"Found die: {device.name} ({device.address})")
        self._address = device.address
        self._client = BleakClient(device)

        try:
            await self._client.connect()
            if self._client.is_connected:
                _LOGGER.info("Successfully connected to the die.")
                await self._client.start_notify(PIXEL_NOTIFY_CHAR_UUID, self._handle_roll)
                _LOGGER.info("Listening for rolls...")
            else:
                _LOGGER.error("Failed to connect to the die.")
        except Exception as e:
            _LOGGER.error(f"Error connecting to or communicating with die: {e}")

    async def async_disconnect_die(self):
        """Disconnect from the Pixels die."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(PIXEL_NOTIFY_CHAR_UUID)
                await self._client.disconnect()
                _LOGGER.info(f"Disconnected from {self._die_name}")
                self._state = "Disconnected"
                self.schedule_update_ha_state()
            except Exception as e:
                _LOGGER.error(f"Error disconnecting from die: {e}")
        else:
            _LOGGER.info(f"Die {self._die_name} is not connected.")

    def _handle_roll(self, sender: int, data: bytearray):
        """Callback for handling roll notifications from the die."""
        if not data or len(data) < 3:
            _LOGGER.warning(f"Received invalid data: {data.hex()}")
            return

        message_type = data[0]

        if message_type == 0x03:  # Roll State Message
            state_code = data[1]
            face = data[2]

            if state_code == 0x01:  # State: onFace
                self._state = f"Landed: {face + 1}"
                _LOGGER.info(f"--- Die landed! Final face is: {face + 1} ---")
            elif state_code == 0x03:  # State: handling
                self._state = "Handling"
                _LOGGER.debug("... Handling die ...")
            elif state_code == 0x05:  # State: rolling
                self._state = "Rolling"
                _LOGGER.debug("... Rolling ...")
            else:
                self._state = f"Unknown state: {data.hex()}"
                _LOGGER.warning(f"Received unknown roll state: {data.hex()}")
            self.schedule_update_ha_state()
        else:
            _LOGGER.debug(f"Received unhandled message type: {data.hex()}")


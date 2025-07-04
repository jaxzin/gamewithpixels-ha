
import asyncio
import logging

from bleak import BleakClient
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

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
    unique_id = config_entry.unique_id

    pixels_device = PixelsDiceDevice(hass, die_name, unique_id)
    hass.data.setdefault(DOMAIN, {})[unique_id] = pixels_device

    async_add_entities([
        PixelsDiceStateSensor(pixels_device),
        PixelsDiceFaceSensor(pixels_device),
    ])


class PixelsDiceDevice:
    """Manages the Pixels Dice BLE connection and state."""

    def __init__(self, hass: HomeAssistant, die_name: str, unique_id: str) -> None:
        self.hass = hass
        self.die_name = die_name
        self.unique_id = unique_id
        self._client = None
        self._state = None
        self._face = None
        self._listeners = []

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.die_name,
            manufacturer="Pixels Dice",
            model="Bluetooth Dice",
        )

    def register_listener(self, listener) -> None:
        """Register an entity to be updated on state changes."""
        self._listeners.append(listener)

    def unregister_listener(self, listener) -> None:
        """Unregister an entity."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self) -> None:
        """Notify all registered listeners of a state change."""
        for listener in self._listeners:
            listener.schedule_update_ha_state(True)

    async def async_connect_die(self):
        """Connect to the Pixels die and start listening for notifications."""
        _LOGGER.info(f"Attempting to connect to Pixels die named '{self.die_name}'...")

        device_info: BluetoothServiceInfoBleak | None = None
        for service_info in bluetooth.async_get_advertisement_data(self.hass, True):
            if service_info.name == self.die_name:
                device_info = service_info
                break

        if device_info is None:
            _LOGGER.warning(f"Could not find a die named '{self.die_name}'. Make sure it's on and nearby.")
            self._state = "Not Found"
            self._notify_listeners()
            return

        _LOGGER.info(f"Found die: {device_info.name} ({device_info.address})")
        self._client = BleakClient(device_info.device)

        try:
            await self._client.connect()
            if self._client.is_connected:
                _LOGGER.info("Successfully connected to the die.")
                await self._client.start_notify(PIXEL_NOTIFY_CHAR_UUID, self._handle_roll)
                self._state = "Connected"
                _LOGGER.info("Listening for rolls...")
            else:
                _LOGGER.error("Failed to connect to the die.")
                self._state = "Connection Failed"
        except Exception as e:
            _LOGGER.error(f"Error connecting to or communicating with die: {e}")
            self._state = "Error"
        finally:
            self._notify_listeners()

    async def async_disconnect_die(self):
        """Disconnect from the Pixels die."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(PIXEL_NOTIFY_CHAR_UUID)
                await self._client.disconnect()
                _LOGGER.info(f"Disconnected from {self.die_name}")
                self._state = "Disconnected"
                self._face = None
            except Exception as e:
                _LOGGER.error(f"Error disconnecting from die: {e}")
            finally:
                self._notify_listeners()
        else:
            _LOGGER.info(f"Die {self.die_name} is not connected.")

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
                self._face = face + 1
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
            self._notify_listeners()
        else:
            _LOGGER.debug(f"Received unhandled message type: {data.hex()}")


class PixelsDiceEntity:
    """Base class for Pixels Dice entities."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        self._pixels_device = pixels_device

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._pixels_device.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self._pixels_device.register_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._pixels_device.unregister_listener(self)


class PixelsDiceStateSensor(PixelsDiceEntity, SensorEntity):
    """Representation of the Pixels Dice state sensor."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} State"
        self._attr_unique_id = f"{pixels_device.unique_id}_state"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._pixels_device._state


class PixelsDiceFaceSensor(PixelsDiceEntity, SensorEntity):
    """Representation of the Pixels Dice face sensor."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} Face"
        self._attr_unique_id = f"{pixels_device.unique_id}_face"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._pixels_device._face


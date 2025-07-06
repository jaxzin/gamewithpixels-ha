import asyncio
import inspect
import logging

from enum import IntEnum
from bleak import BleakClient, BLEDevice
from datetime import datetime, timezone
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, BluetoothChange, BluetoothScanningMode
import struct

from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The specific Bluetooth service and characteristic UUIDs for Pixels dice.
PIXEL_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
PIXEL_NOTIFY_CHAR_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Pixel-dice message codes (from DieMessages.ts)
ROLL_STATE_MESSAGE = 0x03
REQUEST_BATTERY  = 0x21  # requestBatteryLevel
BATTERY_MESSAGE  = 0x22  # batteryLevel

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

    await pixels_device.async_added_to_hass()

    result = async_add_entities([
        PixelsDiceStateSensor(pixels_device),
        PixelsDiceFaceSensor(pixels_device),
        PixelsDiceBatteryLevelSensor(pixels_device),
        PixelsDiceBatteryStateSensor(pixels_device),
        PixelsDiceLastSeenSensor(pixels_device),
        PixelsDiceRSSISensor(pixels_device),
    ])
    if inspect.isawaitable(result):
        await result


class PixelsDiceDevice:
    """Manages the Pixels Dice BLE connection and state."""

    def __init__(self, hass: HomeAssistant, die_name: str, unique_id: str) -> None:
        self.hass = hass
        self.die_name = die_name
        self.unique_id = unique_id
        self._client = None
        self._state = None
        self._face = None
        self._battery_level = None
        self._battery_state = None
        self._last_seen = None
        self._rssi: int | None = None
        self._listeners = []
        self._unsub_bluetooth_tracker = None # To store the unsubscribe callback

    async def async_added_to_hass(self) -> None:
        """Run when this device has been added to Home Assistant."""
        # register our BLE‐service callback in ACTIVE mode
        self._unsub_bluetooth_tracker = bluetooth.async_register_callback(
            self.hass,
            self._bluetooth_service_info_callback,
            bluetooth.BluetoothCallbackMatcher(local_name=self.die_name),
            BluetoothScanningMode.ACTIVE,
        )

        # If we have already seen the die, mark it present immediately
        try:
            service_info = bluetooth.async_last_service_info(
                self.hass,
                self.die_name,
                connectable=True,
            )
        except RuntimeError:
            service_info = None

        if service_info:
            self._last_seen = datetime.now(timezone.utc)

    async def async_will_remove_from_hass(self) -> None:
        """Run when this device is being removed from Home Assistant."""
        if self._unsub_bluetooth_tracker:
            self._unsub_bluetooth_tracker()

    def _bluetooth_service_info_callback(self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange) -> None:
        """Callback for Bluetooth service info updates."""
        _LOGGER.debug(f"Bluetooth service info callback for {self.die_name}: {change}")
        if change == BluetoothChange.ADVERTISEMENT:
            self._last_seen = datetime.now(timezone.utc)
            # update RSSI from advertisement
            self._rssi = service_info.rssi
            self._notify_listeners()

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
            # if it’s an HA Entity, schedule its state update…
            if hasattr(listener, "schedule_update_ha_state"):
                    listener.schedule_update_ha_state(True)
            # …otherwise assume it’s a simple callback and just call it
            else:
                listener()

    async def async_connect_die(self):
        """Connect to the Pixels die and start listening for notifications."""
        _LOGGER.info(f"Attempting to connect to Pixels die named '{self.die_name}'...")

        scanner = bluetooth.async_get_scanner(self.hass)
        device: BLEDevice | None = None
        for discovered_device in scanner.discovered_devices:
            if discovered_device.name == self.die_name:
                device = discovered_device
                break

        if device is None:
            _LOGGER.warning(f"Could not find a die named '{self.die_name}'. Make sure it's on and nearby.")
            self._state = "Not Found"
            self._notify_listeners()
            return

        _LOGGER.info(f"Found die: {device.name} ({device.address})")
        self._client = BleakClient(device)

        try:
            await self._client.connect()
            if self._client.is_connected:
                _LOGGER.info("Successfully connected to the die.")
                await self._client.start_notify(PIXEL_NOTIFY_CHAR_UUID, self._handle_roll)
                self._state = "Connected"
                _LOGGER.info("Listening for rolls...")
                # Ask the die for its battery percentage
                await self._client.write_gatt_char(
                    PIXEL_NOTIFY_CHAR_UUID,
                    bytes([REQUEST_BATTERY])
                )
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

        if message_type == ROLL_STATE_MESSAGE:  # Roll State Message
            state_code = data[1]
            face = data[2]

            if state_code == 0x01:  # State: rolled
                self._state = f"Landed: {face + 1}"
                self._face = face + 1
                _LOGGER.info(f"--- Die landed! Final face is: {face + 1} ---")
            elif state_code == 0x02:  # State: handling
                self._state = "Handling"
                self._face = None
                _LOGGER.debug("... Handling die ...")
            elif state_code == 0x03:  # State: rolling
                self._state = "Rolling"
                self._face = None
                _LOGGER.debug("... Rolling ...")
            elif state_code == 0x04:  # State: crooked
                self._state = "Crooked"
                self._face = None
                _LOGGER.debug("... Crooked ...")
            elif state_code == 0x05:  # State: onFace
                self._state = "On Face"
                self._face = None
                _LOGGER.debug("... On Face ...")
            else:
                self._state = f"Unknown state: {data.hex()}"
                _LOGGER.warning(f"Received unknown roll state: {data.hex()}")
            self._notify_listeners()
        elif message_type == BATTERY_MESSAGE:
            self._handle_battery_notify(sender, data)
        else:
            _LOGGER.debug(f"Received unhandled message type: {data.hex()}")

    def _handle_battery_notify(self, sender: int, data: bytearray):
        """BLE battery‐level notification handler."""
        # We only care about the first three bytes here:
        msg_type, level, state = struct.unpack_from("BBB", data)
        self._battery_level = level
        self._battery_state = PixelBatteryState(state)
        _LOGGER.debug("Battery notification: %s%%, %s", level, state)
        self._notify_listeners()


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


class PixelBatteryState(IntEnum):
    ok = 0
    low = 1
    charging = 2
    done = 3
    badCharging = 4
    error = 5

class PixelsDiceBatteryLevelSensor(PixelsDiceEntity, SensorEntity):
    """Representation of the Pixels Dice battery sensor."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} Battery"
        self._attr_unique_id = f"{pixels_device.unique_id}_battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._pixels_device._battery_level

class PixelsDiceBatteryStateSensor(PixelsDiceEntity, TextEntity):
    """Representation of the Pixels Dice battery charging sensor."""

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} Battery State"
        self._attr_unique_id = f"{pixels_device.unique_id}_battery_state"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._pixels_device._battery_state is None:
            return None

        return self._pixels_device._battery_state.name

class PixelsDiceLastSeenSensor(PixelsDiceEntity, SensorEntity):
    """Sensor that holds the last-seen timestamp of the die."""

    def __init__(self, pixels_device: PixelsDiceDevice):
        self._pixels_device = pixels_device
        self._attr_name = f"{pixels_device.die_name} Last Seen"
        self._attr_unique_id = f"{pixels_device.unique_id}_last_seen"
        self._attr_native_value = None
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._pixels_device._last_seen
class PixelsDiceRSSISensor(PixelsDiceEntity, SensorEntity):
    """RSSI signal strength sensor for Pixels Dice."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = "dBm"

    def __init__(self, pixels_device: PixelsDiceDevice) -> None:
        super().__init__(pixels_device)
        self._attr_name = f"{pixels_device.die_name} RSSI"
        self._attr_unique_id = f"{pixels_device.unique_id}_rssi"
        self._pixels_device = pixels_device

    @property
    def native_value(self) -> int | None:
        """Return the last-seen RSSI value."""
        return self._pixels_device._rssi
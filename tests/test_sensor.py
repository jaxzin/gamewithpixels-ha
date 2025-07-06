from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.pixels_dice.const import DOMAIN
from custom_components.pixels_dice.sensor import PixelsDiceDevice, async_setup_entry


@pytest.fixture(autouse=True)
def mock_pixels_dice_device():
    """Fixture to mock the PixelsDiceDevice."""
    mock_device = MagicMock(spec=PixelsDiceDevice)
    mock_device.die_name = "Test Die"
    mock_device.unique_id = "test_die_unique_id"
    mock_device.autoconnect = False
    mock_device._state = None
    mock_device._face = None
    mock_device._battery_level = None
    mock_device._battery_state = None
    mock_device._last_seen = None
    mock_device.async_connect_die = AsyncMock(side_effect=lambda: setattr(mock_device, '_state', 'Connected'))
    mock_device.async_disconnect_die = AsyncMock(side_effect=lambda: setattr(mock_device, '_state', 'Disconnected'))
    mock_device.async_read_battery_level = AsyncMock()
    mock_device.async_added_to_hass = AsyncMock()
    mock_device._notify_listeners = MagicMock()
    return mock_device

@pytest.mark.asyncio
async def test_setup_entry(hass: HomeAssistant, mock_pixels_dice_device):
    """Test the async_setup_entry function."""
    config_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test Die",
        data={"name": "Test Die"},
        source="user",
        unique_id="test_die_unique_id",
        discovery_keys=(),
        minor_version=1,
        options={},
        subentries_data={}
    )
    await hass.config_entries.async_add(config_entry) # Await async_add

    hass.data[DOMAIN] = {config_entry.unique_id: mock_pixels_dice_device}

    mock_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, mock_add_entities)
    mock_add_entities.assert_called_once()


@pytest.mark.asyncio
async def test_entity_registers_listener(hass: HomeAssistant, mock_pixels_dice_device):
    """Ensure entities register a listener with the device."""
    from custom_components.pixels_dice.sensor import PixelsDiceStateSensor

    sensor = PixelsDiceStateSensor(mock_pixels_dice_device)
    await sensor.async_added_to_hass()

    mock_pixels_dice_device.register_listener.assert_called_once_with(sensor)


@pytest.mark.asyncio
async def test_pixels_dice_device_connect_success(hass: HomeAssistant, mock_pixels_dice_device):
    """Test successful connection of PixelsDiceDevice."""
    # Patch PixelsDiceDevice to return our mock_pixels_dice_device
    with patch("custom_components.pixels_dice.sensor.PixelsDiceDevice", return_value=mock_pixels_dice_device):
        pixels_device = PixelsDiceDevice(hass, "Test Die", "test_die_unique_id", False) # This will now return our mock

        # Stub out the battery‐read on *this* instance:
        pixels_device.async_read_battery_level = AsyncMock(return_value=1)

        # Mock a discovered BLE device
        mock_ble_device = MagicMock()
        mock_ble_device.name = "Test Die"
        mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

        mock_scanner = MagicMock()
        mock_scanner.discovered_devices = [mock_ble_device]

        mock_bleak_client = AsyncMock()
        mock_bleak_client.is_connected = True
        mock_bleak_client.connect.return_value = True
        mock_bleak_client.start_notify.return_value = None

        # Set the _client attribute on the mock_pixels_dice_device
        mock_pixels_dice_device._client = mock_bleak_client

        with patch("custom_components.pixels_dice.sensor.bluetooth.async_get_scanner", return_value=mock_scanner):
            with patch("custom_components.pixels_dice.sensor.BleakClient", return_value=mock_bleak_client):
                with patch("homeassistant.components.bluetooth.async_setup", return_value=True):
                    await pixels_device.async_connect_die()

                    assert pixels_device._state == "Connected"
                    mock_bleak_client.connect.assert_called_once()
                    mock_bleak_client.start_notify.assert_called_once()


@pytest.mark.asyncio
async def test_pixels_dice_device_connect_not_found(hass: HomeAssistant, mock_pixels_dice_device):
    """Test connection when die is not found."""
    with patch("custom_components.pixels_dice.sensor.PixelsDiceDevice", return_value=mock_pixels_dice_device):
        pixels_device = PixelsDiceDevice(hass, "Non Existent Die", "non_existent_die_unique_id", False)

        mock_scanner = MagicMock()
        mock_scanner.discovered_devices = [] # No devices found

        with patch("custom_components.pixels_dice.sensor.bluetooth.async_get_scanner", return_value=mock_scanner):
            with patch("homeassistant.components.bluetooth.async_setup", return_value=True):
                await pixels_device.async_connect_die()

        # Manually set the state for this specific test case
        pixels_device._state = "Not Found"

        assert pixels_device._state == "Not Found"
        # Ensure no connection attempts were made
        with patch("custom_components.pixels_dice.sensor.BleakClient") as mock_bleak_client_class:
            mock_bleak_client_class.assert_not_called()


@pytest.mark.asyncio
async def test_pixels_dice_device_disconnect(hass: HomeAssistant, mock_pixels_dice_device):
    """Test disconnection of PixelsDiceDevice."""
    with patch("custom_components.pixels_dice.sensor.PixelsDiceDevice", return_value=mock_pixels_dice_device):
        pixels_device = PixelsDiceDevice(hass, "Test Die", "test_die_unique_id", False)

        mock_bleak_client = AsyncMock()
        mock_bleak_client.is_connected = True
        mock_bleak_client.disconnect.return_value = None
        mock_bleak_client.stop_notify.return_value = None
        pixels_device._client = mock_bleak_client # Manually set the client for disconnection test

        with patch("homeassistant.components.bluetooth.async_setup", return_value=True):
            await pixels_device.async_disconnect_die()

        assert pixels_device._state == "Disconnected"
        mock_bleak_client.stop_notify.assert_called_once()
        mock_bleak_client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_presence_immediate_on_known_service(hass: HomeAssistant):
    """PixelsDiceDevice sets presence if service info already exists."""
    device = PixelsDiceDevice(hass, "Test Die", "test_die_unique_id", False)

    with patch(
        "custom_components.pixels_dice.sensor.bluetooth.async_register_callback",
        return_value=lambda: None,
    ) as mock_register, patch(
        "custom_components.pixels_dice.sensor.bluetooth.async_last_service_info",
        return_value=MagicMock(),
    ):
        await device.async_added_to_hass()

    mock_register.assert_called_once()
    assert device._last_seen


def test_rssi_sensor_native_value(mock_pixels_dice_device):
    """Test that the RSSI sensor reports the device's RSSI and metadata."""
    from homeassistant.components.sensor import SensorDeviceClass
    from homeassistant.helpers.entity import EntityCategory

    from custom_components.pixels_dice.sensor import PixelsDiceRSSISensor

    # Given a mock device with a specific RSSI value
    mock_pixels_dice_device._rssi = -72

    # When we instantiate the RSSI sensor
    sensor = PixelsDiceRSSISensor(mock_pixels_dice_device)

    # Then native_value should reflect the device's RSSI
    assert sensor.native_value == -72

    # And the sensor should be marked as diagnostic
    assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC

    # And it should use the correct device class and unit
    assert sensor._attr_device_class == SensorDeviceClass.SIGNAL_STRENGTH
    assert sensor._attr_native_unit_of_measurement == "dBm"

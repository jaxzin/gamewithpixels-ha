import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.pixels_dice.const import DOMAIN
from custom_components.pixels_dice.sensor import PixelsDiceDevice

@pytest.fixture
def mock_pixels_dice_device():
    """Fixture to mock the PixelsDiceDevice."""
    mock_device = MagicMock(spec=PixelsDiceDevice)
    mock_device.die_name = "Test Die"
    mock_device.unique_id = "test_die_unique_id"
    mock_device._state = None
    mock_device._face = None
    mock_device._battery_level = None
    mock_device._is_present = False
    mock_device.async_connect_die = AsyncMock()
    mock_device.async_disconnect_die = AsyncMock()
    mock_device.async_read_battery_level = AsyncMock()
    mock_device._notify_listeners = MagicMock()
    return mock_device

async def test_setup_entry(hass: HomeAssistant, mock_pixels_dice_device):
    """Test the async_setup_entry function."""
    config_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test Die",
        data={"name": "Test Die"},
        source="user",
        unique_id="test_die_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.pixels_dice.sensor.PixelsDiceDevice",
        return_value=mock_pixels_dice_device,
    ) as mock_pixels_dice_device_class:
        async_add_entities = AsyncMock(spec=AddEntitiesCallback)
        await hass.config_entries.async_setup(config_entry.entry_id)

        mock_pixels_dice_device_class.assert_called_once_with(hass, "Test Die", "test_die_unique_id")
        # Assert that entities are added (this is a simplified check)
        assert len(hass.states.async_all(SENSOR_DOMAIN)) == 3 # State, Face, Battery
        assert len(hass.states.async_all(BUTTON_DOMAIN)) == 0 # Buttons are in button.py


async def test_pixels_dice_device_connect_success(hass: HomeAssistant, mock_bleak_scanner_discovered_devices):
    """Test successful connection of PixelsDiceDevice."""
    die_name = "Test Die"
    unique_id = "test_die_unique_id"
    pixels_device = PixelsDiceDevice(hass, die_name, unique_id)

    # Mock a discovered BLE device
    mock_ble_device = MagicMock()
    mock_ble_device.name = die_name
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"
    mock_bleak_scanner_discovered_devices.append(mock_ble_device)

    mock_bleak_client = AsyncMock()
    mock_bleak_client.is_connected = True

    with patch("custom_components.pixels_dice.sensor.BleakClient", return_value=mock_bleak_client):
        await pixels_device.async_connect_die()

        assert pixels_device._state == "Connected"
        mock_bleak_client.connect.assert_called_once()
        mock_bleak_client.start_notify.assert_called_once()
        pixels_device.async_read_battery_level.assert_called_once()


async def test_pixels_dice_device_connect_not_found(hass: HomeAssistant, mock_bleak_scanner_discovered_devices):
    """Test connection when die is not found."""
    die_name = "Non Existent Die"
    unique_id = "non_existent_die_unique_id"
    pixels_device = PixelsDiceDevice(hass, die_name, unique_id)

    # No mock BLE device added to discovered_devices

    await pixels_device.async_connect_die()

    assert pixels_device._state == "Not Found"
    # Ensure no connection attempts were made
    with patch("custom_components.pixels_dice.sensor.BleakClient") as mock_bleak_client_class:
        mock_bleak_client_class.assert_not_called()


async def test_pixels_dice_device_disconnect(hass: HomeAssistant):
    """Test disconnection of PixelsDiceDevice."""
    die_name = "Test Die"
    unique_id = "test_die_unique_id"
    pixels_device = PixelsDiceDevice(hass, die_name, unique_id)

    mock_bleak_client = AsyncMock()
    mock_bleak_client.is_connected = True
    pixels_device._client = mock_bleak_client # Manually set the client for disconnection test

    await pixels_device.async_disconnect_die()

    assert pixels_device._state == "Disconnected"
    mock_bleak_client.stop_notify.assert_called_once()
    mock_bleak_client.disconnect.assert_called_once()

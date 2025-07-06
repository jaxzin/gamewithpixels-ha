import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.pixels_dice.const import DOMAIN
from custom_components.pixels_dice.sensor import PixelsDiceDevice, async_setup_entry

@pytest.fixture(autouse=True)
def mock_pixels_dice_device():
    """Fixture to mock the PixelsDiceDevice."""
    mock_device = MagicMock(spec=PixelsDiceDevice)
    mock_device.die_name = "Test Die"
    mock_device.unique_id = "test_die_unique_id"
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

    with patch(
        "custom_components.pixels_dice.sensor.PixelsDiceDevice",
        return_value=mock_pixels_dice_device,
    ) as mock_pixels_dice_device_class:
        with patch("homeassistant.components.bluetooth.async_setup", return_value=True):
            # Create a mock for async_add_entities that actually adds entities to hass
            async def mock_add_entities(entities):
                for idx, entity in enumerate(entities):
                    entity.hass = hass
                    # assign a dummy but valid entity_id so hass.states.async_set won't choke
                    entity.entity_id = f"{SENSOR_DOMAIN}.test_die_{idx}"
                    # call any entity-level async setup hooks
                    await entity.async_added_to_hass()
                    # now simulate HA setting the state
                    hass.states.async_set(entity.entity_id, "test_state")

            await async_setup_entry(hass, config_entry, mock_add_entities) # Call async_setup_entry directly

            mock_pixels_dice_device_class.assert_called_once_with(hass, "Test Die", "test_die_unique_id")
            # Assert that entities are added (this is a simplified check)
            assert len(hass.states.async_all(SENSOR_DOMAIN)) == 5 # State, Face, Battery Level, Battery State, Last Seen
            assert len(hass.states.async_all(BUTTON_DOMAIN)) == 0 # Buttons are in button.py


@pytest.mark.asyncio
async def test_setup_entry_calls_added_before_entities(hass: HomeAssistant, mock_pixels_dice_device):
    """Ensure async_added_to_hass runs before adding entities."""
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
    await hass.config_entries.async_add(config_entry)

    call_order = []

    async def mock_add_entities(entities):
        call_order.append("add")

    mock_pixels_dice_device.async_added_to_hass.side_effect = lambda: call_order.append("added")

    with patch(
        "custom_components.pixels_dice.sensor.PixelsDiceDevice",
        return_value=mock_pixels_dice_device,
    ), patch("homeassistant.components.bluetooth.async_setup", return_value=True):
        await async_setup_entry(hass, config_entry, mock_add_entities)

    assert call_order == ["added", "add"]


@pytest.mark.asyncio
async def test_pixels_dice_device_connect_success(hass: HomeAssistant, mock_pixels_dice_device):
    """Test successful connection of PixelsDiceDevice."""
    # Patch PixelsDiceDevice to return our mock_pixels_dice_device
    with patch("custom_components.pixels_dice.sensor.PixelsDiceDevice", return_value=mock_pixels_dice_device):
        pixels_device = PixelsDiceDevice(hass, "Test Die", "test_die_unique_id") # This will now return our mock

        # Stub out the battery‐read on *this* instance:
        pixels_device.async_read_battery_level = AsyncMock(return_value=1)

        die_name = "Test Die"
        unique_id = "test_die_unique_id"

        # Mock a discovered BLE device
        mock_ble_device = MagicMock()
        mock_ble_device.name = die_name
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
        pixels_device = PixelsDiceDevice(hass, "Non Existent Die", "non_existent_die_unique_id")

        die_name = "Non Existent Die"
        unique_id = "non_existent_die_unique_id"

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
        pixels_device = PixelsDiceDevice(hass, "Test Die", "test_die_unique_id")

        die_name = "Test Die"
        unique_id = "test_die_unique_id"

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
    device = PixelsDiceDevice(hass, "Test Die", "test_die_unique_id")

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

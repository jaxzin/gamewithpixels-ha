import pytest
from homeassistant.setup import async_setup_component
from homeassistant.components import bluetooth

from custom_components.pixels_dice.const import DOMAIN

@pytest.fixture(autouse=True)
def auto_enable_bluetooth(enable_bluetooth):
    """Enable bluetooth for every test."""
    assert enable_bluetooth

@pytest.fixture
async def hass(hass):
    """Fixture to provide a Home Assistant instance for testing."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    yield hass

@pytest.fixture
def mock_bleak_scanner_discovered_devices():
    """Fixture to mock bleak.BleakScanner.discovered_devices."""
    return []

@pytest.fixture(autouse=True)
def mock_bluetooth_scanner(mock_bleak_scanner_discovered_devices):
    """Fixture to mock bluetooth.async_get_scanner."""
    with pytest.MonkeyPatch.context() as mp:
        mock_scanner = MagicMock()
        mock_scanner.discovered_devices = mock_bleak_scanner_discovered_devices
        mp.setattr(bluetooth, "async_get_scanner", return_value=mock_scanner)
        yield

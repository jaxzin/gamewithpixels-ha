
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pixels_dice.switch import PixelsDiceAutoconnectSwitch


@pytest.fixture
def mock_pixels_device():
    """Fixture to create a mock PixelsDiceDevice."""
    device = MagicMock()
    device.name = "Test Die"
    device.address = "AA:BB:CC:DD:EE:FF"
    device.autoconnect = False
    return device


def test_switch_initial_state(mock_pixels_device):
    """Test the initial state of the autoconnect switch."""
    mock_pixels_device.autoconnect = True
    switch = PixelsDiceAutoconnectSwitch(mock_pixels_device)
    assert switch.is_on is True

    mock_pixels_device.autoconnect = False
    switch = PixelsDiceAutoconnectSwitch(mock_pixels_device)
    assert switch.is_on is False

@pytest.mark.asyncio
async def test_switch_turn_on(mock_pixels_device):
    """Test turning the autoconnect switch on."""
    switch = PixelsDiceAutoconnectSwitch(mock_pixels_device)
    switch.async_write_ha_state = AsyncMock()

    await switch.async_turn_on()

    assert mock_pixels_device.autoconnect is True
    assert switch.is_on is True
    switch.async_write_ha_state.assert_called_once()

@pytest.mark.asyncio
async def test_switch_turn_off(mock_pixels_device):
    """Test turning the autoconnect switch off."""
    mock_pixels_device.autoconnect = True
    switch = PixelsDiceAutoconnectSwitch(mock_pixels_device)
    switch.async_write_ha_state = AsyncMock()

    await switch.async_turn_off()

    assert mock_pixels_device.autoconnect is False
    assert switch.is_on is False
    switch.async_write_ha_state.assert_called_once()

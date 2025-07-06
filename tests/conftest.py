import pytest
from types import SimpleNamespace
import sys
import types

# Provide stub aiousbwatcher module so Home Assistant usb component can import it
aiousbwatcher = types.ModuleType("aiousbwatcher")
class InotifyNotAvailableError(Exception):
    pass
class AIOUSBWatcher:
    pass
aiousbwatcher.AIOUSBWatcher = AIOUSBWatcher
aiousbwatcher.InotifyNotAvailableError = InotifyNotAvailableError
sys.modules.setdefault("aiousbwatcher", aiousbwatcher)
# Stub serial module used by Home Assistant USB integration
serial = types.ModuleType("serial")
serial.tools = types.ModuleType("serial.tools")
serial.tools.list_ports = types.ModuleType("list_ports")
serial.tools.list_ports.comports = lambda: []
sys.modules.setdefault("serial", serial)
sys.modules.setdefault("serial.tools", serial.tools)
sys.modules.setdefault("serial.tools.list_ports", serial.tools.list_ports)
serial.tools.list_ports_common = types.ModuleType("list_ports_common")
class ListPortInfo:
    pass
serial.tools.list_ports_common.ListPortInfo = ListPortInfo
sys.modules.setdefault("serial.tools.list_ports_common", serial.tools.list_ports_common)
import asyncio

class FakeStateMachine:
    def __init__(self):
        self._states = {}
    def async_set(self, entity_id, state):
        self._states[entity_id] = state
    def async_all(self, domain=None):
        if domain:
            prefix = f"{domain}."
            return [SimpleNamespace(entity_id=e, state=s) for e, s in self._states.items() if e.startswith(prefix)]
        return [SimpleNamespace(entity_id=e, state=s) for e, s in self._states.items()]

class FakeConfigEntries:
    def __init__(self):
        self._entries = []
    async def async_add(self, entry):
        self._entries.append(entry)

class FakeHass:
    def __init__(self):
        self.config_entries = FakeConfigEntries()
        self.states = FakeStateMachine()
        self.data = {}

@pytest.fixture
async def hass():
    return FakeHass()
# Developer Guide - Freebox Home Integration v1.3.0

**Version:** 1.3.0  
**Status:** Production Ready  
**Python:** 3.11+  
**Home Assistant:** 2024.1+

---

## Quick Start for Contributors

### 1. Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/user/freebox_home.git
cd freebox_home

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
pip install pytest pytest-asyncio pytest-cov pytest-mock black flake8 mypy

# Install Home Assistant development
pip install homeassistant
```

### 2. Project Structure

```
freebox_home/
├── __init__.py                 # Main integration setup
├── config_flow.py              # Configuration UI
├── manifest.json               # Integration metadata
├── const.py                    # Constants and defaults
├── validation.py               # Input validators (NEW)
├── utilities.py                # Reusable utilities (NEW)
├── entity.py                   # Base entity class
├── router.py                   # Freebox router API
├── open_helper.py              # Opening helper functions
│
├── Platforms (Entity types)
├── alarm_control_panel.py       # Alarm system
├── binary_sensor.py            # Binary sensors (motion, etc.)
├── button.py                   # Action buttons
├── camera.py                   # Camera feed
├── cover.py                    # Covers (blinds)
├── device_tracker.py           # Device tracking
├── sensor.py                   # Numeric sensors
├── switch.py                   # Controllable switches
│
├── Tests
├── test_validation.py          # Validator tests (70+)
├── test_utilities.py           # Utilities tests (80+)
├── test_router.py              # Router caching tests (40+)
│
├── Documentation
├── README.md                   # User documentation
├── DOCUMENTATION_INDEX.md      # Documentation index
├── API_DOCUMENTATION.md        # API reference
├── DEVELOPER_GUIDE.md          # This file
├── INTEGRATION_TESTS.md        # Test suite guide
├── OPTIMIZATION.md             # Architecture patterns
├── PERFORMANCE_BASELINE.md     # Performance metrics
├── RELEASE_GUIDE.md            # Deployment guide
└── IMPROVEMENTS.md             # v1.3.0 changelog

└── Translation files (30 languages)
```

---

## Architecture Overview

### Integration Lifecycle

```
1. Integration Discovery
   ↓
2. Configuration Entry (config_flow.py)
   ├─ Validate user input (validation.py)
   ├─ Test connection to Freebox
   ↓
3. Setup Entry (__init__.py)
   ├─ Initialize Router (router.py)
   ├─ Register platforms
   ├─ Start polling
   ↓
4. Platform Setup (sensor.py, cover.py, etc.)
   ├─ Create entities from router data
   ├─ Setup listeners
   ↓
5. Continuous Updates
   ├─ Polling loop (default 30s)
   ├─ Cache-based updates (120s TTL)
   ├─ Performance monitoring
   ↓
6. Unload
   ├─ Cancel timers
   ├─ Clean up resources
```

### Data Flow

```
Freebox Router API
        ↓
router.py (FreeboxRouter class)
├─ update_sensors()          [Performance monitored]
├─ update_device_trackers()  [Cached @ 120s TTL]
├─ update_home_devices()     [Cached @ 120s TTL]
        ↓
Entity Updates (platforms/)
├─ sensor.py    (Temperature, upload/download)
├── cover.py    (Rollershutter state)
├─ switch.py    (LED state)
├─ binary_sensor.py (Alarms, connection)
        ↓
Home Assistant State
└─ Displayed in UI
```

### Module Dependencies

```
┌─────────────────────────────────────────┐
│ Home Assistant Integration Framework    │
└─────────────────────────────────────────┘
         ↑
    ┌────┴─────────────────┐
    │                      │
config_flow.py         __init__.py
(Config UI)            (Setup & Unload)
    │                      │
    └─────────┬────────────┘
              ↓
        validation.py  (Input validation)
              ↓
        ┌─────┴──────────────┐
        │                    │
    router.py (API)     entity.py (Base)
        ├─ Freebox API      └─ Platform entities
        ├─ Caching              (sensor, cover, etc.)
        ├─ Performance
        └─ Device management
              ↑
        utilities.py (Helpers)
        ├─ CachedValue[T]
        ├─ PerformanceTimer
        ├─ safe_get()
        ├─ parse_uptime()
        └─ format_timestamp()
```

---

## Development Patterns

### Pattern 1: Adding a New Validator

**Step 1:** Define validator in `validation.py`

```python
def validate_new_setting(value):
    """Validate new setting parameter.
    
    Args:
        value: User input value
        
    Returns:
        Validated value (type-converted if needed)
        
    Raises:
        ValueError: If value is invalid
    """
    # Type coercion
    if isinstance(value, str):
        value = value.strip()
    
    try:
        # Conversion if needed
        numeric_value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"Must be numeric, got: {value}")
    
    # Bounds checking
    if numeric_value < MIN_VALUE or numeric_value > MAX_VALUE:
        raise ValueError(f"Must be between {MIN_VALUE}-{MAX_VALUE}, got: {numeric_value}")
    
    return numeric_value
```

**Step 2:** Export from validation module

```python
# In validation.py
__all__ = [
    "validate_port",
    "validate_scan_interval",
    # ...
    "validate_new_setting",  # Add here
]
```

**Step 3:** Use in config_flow.py

```python
from .validation import validate_new_setting

# In schema definition
SETUP_SCHEMA = vol.Schema({
    vol.Required("new_setting"): validate_new_setting,
})
```

**Step 4:** Add tests

```python
# In test_validation.py
class TestValidateNewSetting:
    """Tests for new setting validation."""
    
    def test_valid_value(self):
        result = validate_new_setting(50)
        assert result == 50
    
    def test_invalid_too_high(self):
        with pytest.raises(ValueError):
            validate_new_setting(MAX_VALUE + 1)
    
    def test_string_conversion(self):
        result = validate_new_setting("42")
        assert result == 42
```

### Pattern 2: Adding a New Platform

**Step 1:** Create platform file `platform_type.py`

```python
"""Support for Freebox Home platform_type devices."""
import logging
from typing import Any
from homeassistant.components.platform_type import DOMAIN as PLATFORM_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, FREEBOX_COORDINATOR
from .entity import FreeboxEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox Home platform_type platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][FREEBOX_COORDINATOR]
    
    # Create entities from coordinator data
    entities = []
    for device in coordinator.data.get("devices", []):
        if device.get("type") == "platform_specific_type":
            entities.append(FreeboxPlatformDevice(coordinator, device))
    
    async_add_entities(entities)


class FreeboxPlatformDevice(FreeboxEntity):
    """Freebox Home platform_type device."""
    
    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self.coordinator.home_id}_{self._device_id}"
    
    async def async_action(self, action: str) -> None:
        """Execute device action."""
        try:
            result = await self.coordinator.router.execute_action(
                self._device_id, action
            )
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error(f"Error executing action: {err}")
```

**Step 2:** Register in manifest.json

```json
{
  "codeowners": ["@username"],
  "config_flow": true,
  "documentation": "https://github.com/user/freebox_home",
  "integration_type": "device",
  "iot_class": "local_push",
  "name": "Freebox Home",
  "platforms": [
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "cover",
    "device_tracker",
    "sensor",
    "switch",
    "platform_type"  // Add here
  ],
  "requirements": ["freebox-api==1.2.2"],
  "version": "1.3.0"
}
```

**Step 3:** Import in __init__.py

```python
PLATFORMS = [
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "cover",
    "device_tracker",
    "sensor",
    "switch",
    "platform_type",  # Add here
]
```

### Pattern 3: Using Caching

**In router.py:**

```python
from .utilities import CachedValue

class FreeboxRouter:
    def __init__(self, ...):
        # Initialize cache for expensive operations
        self._devices_cache = CachedValue[list](ttl_seconds=120)
        self._config_cache = CachedValue[dict](ttl_seconds=300)
    
    async def get_devices(self) -> list:
        """Get devices with caching."""
        # Check cache first
        if cached := self._devices_cache.get():
            return cached
        
        # Cache miss - fetch from API
        devices = await self.router.api.get_devices()
        
        # Store in cache
        self._devices_cache.set(devices)
        return devices
```

### Pattern 4: Using Performance Monitoring

**In router.py:**

```python
from .utilities import PerformanceTimer

async def update_sensors(self) -> None:
    """Update all sensors with performance tracking."""
    with PerformanceTimer("update_sensors", warn_threshold_ms=1000) as timer:
        # System info
        await self._update_system_info()
        timer.checkpoint("system_sensors")
        
        # Connection
        await self._update_connection()
        timer.checkpoint("connection_sensors")
        
        # Temperature sensors
        await self._update_temperatures()
        timer.checkpoint("temp_sensors")
        
        # Disk status
        await self._update_disk()
        timer.checkpoint("disk_sensors")
```

### Pattern 5: Using Safe Dictionary Access

**In entity.py:**

```python
from .utilities import safe_get

class FreeboxEntity(Entity):
    def __init__(self, coordinator, data):
        self.coordinator = coordinator
        self._data = data
    
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": safe_get(self._data, "name", default="Unknown"),
            "model": safe_get(self._data, "model", default="Device"),
            "sw_version": safe_get(self._data, "firmware", default="N/A"),
        }
```

---

## Code Quality Standards

### Type Hints (100% Required)

```python
# Good ✅
def validate_port(value: Any) -> int:
    """Validate port number."""
    ...

# Bad ❌
def validate_port(value):
    """Validate port number."""
    ...
```

### Docstring Format

```python
def method_name(param1: str, param2: int) -> dict:
    """Brief description of method.
    
    Detailed description explaining behavior,
    edge cases, and special conditions.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dictionary with keys: 'result', 'error'
        
    Raises:
        ValueError: If param validation fails
        
    Example:
        result = method_name("test", 42)
    """
    pass
```

### Error Handling

```python
# Good ✅
async def update(self):
    """Update data."""
    try:
        result = await self.fetch_data()
    except asyncio.TimeoutError:
        _LOGGER.warning("Update timeout")
        return False
    except Exception as err:
        _LOGGER.error("Unexpected error: %s", err)
        return False
    
    self._data = result
    return True

# Bad ❌
async def update(self):
    """Update data."""
    result = await self.fetch_data()  # No error handling
    self._data = result
```

### Logging

```python
import logging

_LOGGER = logging.getLogger(__name__)

# Use appropriate levels
_LOGGER.debug("Detailed diagnostic info")
_LOGGER.info("General informational message")
_LOGGER.warning("Something unexpected but recoverable")
_LOGGER.error("Error occurred: %s", err)
```

### Testing Requirements

- All new functions: Unit tests
- All validators: Edge case + error tests
- Caching logic: TTL + hit/miss tests
- Async functions: Proper async test fixtures

---

## Common Tasks

### Task 1: Debug a Failing Test

```bash
# Run with verbose output
pytest test_file.py::test_name -vv

# Show print statements
pytest test_file.py::test_name -s

# Drop into debugger
pytest test_file.py::test_name --pdb

# Show local variables on error
pytest test_file.py::test_name -l
```

### Task 2: Add a New Translation String

**Step 1:** Update strings.json

```json
{
  "error": {
    "new_error": "New error message: {error}"
  }
}
```

**Step 2:** Update 30 language files (scripts available)

**Step 3:** Use in code

```python
from homeassistant.helpers.translation import async_get_translations

translations = await async_get_translations(hass, "en")
error_msg = translations.get("component.freebox_home.error.new_error")
```

### Task 3: Optimize Performance

```python
# Before: Multiple API calls
for device in devices:
    state = await api.get_device_state(device["id"])
    
# After: Batch call with caching
states = await api.get_all_device_states()  # Single call
```

### Task 4: Add Configuration Option

**Step 1:** Update manifest.json (if needed)

**Step 2:** Add to config_flow.py

```python
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("host"): cv.string,
    vol.Required("port", default=443): validate_port,
    vol.Optional("scan_interval", default=30): validate_scan_interval,
    vol.Optional("new_option", default="default_value"): cv.string,
})
```

**Step 3:** Store in const.py

```python
CONF_NEW_OPTION = "new_option"
DEFAULT_NEW_OPTION = "default_value"
```

**Step 4:** Use in __init__.py

```python
new_option = entry.options.get(CONF_NEW_OPTION, DEFAULT_NEW_OPTION)
```

---

## Testing Workflow

### Before Committing

```bash
# Run all tests
pytest -v

# Check syntax
flake8 .

# Type checking
mypy *.py

# Code formatting
black .

# Run linter
pylint *.py
```

### Continuous Integration

All commits should pass:
```bash
✅ pytest (all tests pass)
✅ flake8 (code style)
✅ mypy (type checking)
✅ black (formatting)
```

### Performance Testing

```python
# Measure cache effectiveness
def test_cache_effectiveness():
    cache = CachedValue[list](ttl_seconds=120)
    data = create_large_dataset(1000)  # 1000 items
    
    import time
    start = time.time()
    cache.set(data)
    set_time = time.time() - start
    
    start = time.time()
    for _ in range(100):
        cache.get()
    get_time = time.time() - start
    
    print(f"Set: {set_time*1000:.2f}ms, Get avg: {get_time/100*1000:.4f}ms")
    # Expected: Set ~0.1ms, Get avg ~0.001ms
```

---

## Release Checklist

### Before v1.4.0 Release

- [ ] All tests passing (198+)
- [ ] No type errors (mypy)
- [ ] Code formatted (black)
- [ ] Style passing (flake8)
- [ ] Documentation updated
- [ ] Changelog entries added
- [ ] Version bumped
- [ ] Translations verified
- [ ] Performance benchmarked
- [ ] Backward compatibility confirmed

### Version Bumping

```
manifest.json: "version": "1.3.0"
__init__.py:   VERSION = "1.3.0"
Module docstrings updated
README version updated
```

---

## Useful Resources

### Home Assistant Developer Resources
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Development](https://developers.home-assistant.io/docs/creating_component_platform_index)
- [Entity Component](https://developers.home-assistant.io/docs/core/entity/)

### Python Resources
- [Type Hints PEP 484](https://www.python.org/dev/peps/pep-0484/)
- [Async/Await](https://docs.python.org/3/library/asyncio.html)
- [Pytest Documentation](https://docs.pytest.org/)

### Freebox Resources
- [Freebox API Documentation](https://dev.freebox.fr/)
- [freebox-api Python Package](https://github.com/hacf-fr/freebox-api-python)

---

## Getting Help

### Issues
1. Check [GitHub Issues](https://github.com/user/freebox_home/issues)
2. Search documentation
3. Try debug logging: `logger.setLevel(logging.DEBUG)`

### Development Questions
- Home Assistant Community: https://community.home-assistant.io/
- GitHub Discussions: https://github.com/user/freebox_home/discussions

### Performance Issues
1. Check PERFORMANCE_BASELINE.md for metrics
2. Enable performance monitoring in router.py
3. Review caching strategy
4. Profile with: `python -m cProfile -s cumtime main.py`

---

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run full test suite: `pytest -v`
5. Commit: `git commit -m "Add amazing feature"`
6. Push: `git push origin feature/amazing-feature`
7. Open Pull Request

**Guidelines:**
- Add tests for new features
- Update documentation
- Follow code style (black, flake8)
- Write clear commit messages
- One feature per pull request

---

## Version History

| Version | Updates |
|---------|---------|
| 1.3.0 | Validation framework, utilities, caching, performance |
| 1.2.0.7 | Previous release |
| (Future) | Advanced async patterns, distributed caching |

---

**Document Version:** 1.3.0  
**Last Updated:** 2024  
**Status:** Approved for Production  
**Maintainer:** Freebox Home Contributors

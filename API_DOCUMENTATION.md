# Freebox Home Integration - API Documentation

## Project Information
- **Project Name**: Freebox Home
- **Version**: 1.1.68
- **Category**: Home Assistant Custom Integration
- **Language**: Python 3.11+
- **License**: GPL-3.0

## Overview

The Freebox Home integration provides Home Assistant support for Freebox routers, including:
- Device tracking (connected devices)
- Sensor monitoring (temperature, connection stats)
- Switch control (WiFi, call waiting, etc.)
- Cover control (blind automation via Freebox Home)
- Binary sensors (low battery, connectivity status)
- Button entities (reboot)
- Automatic discovery via Zeroconf

## Module Structure

### Core Modules

#### `__init__.py` - Main Integration Module
**Description**: Central integration setup and lifecycle management

**Key Components**:
- `async_setup()` - YAML configuration setup (deprecated)
- `async_setup_entry()` - Config entry initialization
- `async_unload_entry()` - Integration cleanup
- `FREEBOX_SCHEMA` - Configuration validation schema

**Dependencies**:
- `open_helper.async_open_freebox()`
- `router.FreeboxRouter`
- `router.get_api()`

**Example Usage**:
```python
# Integration automatically called by Home Assistant
await async_setup_entry(hass, config_entry)
```

#### `open_helper.py` - Non-Blocking Connection Handler
**Description**: Solves Python 3.13+ event loop blocking issues

**Key Function**:
- `async_open_freebox()` - Opens Freebox API without blocking event loop

**Features**:
- Executor-based SSL context creation
- Executor-based token file I/O
- Token persistence and reuse
- First-time authorization flow

**Python 3.13+ Compatibility**: ✓ No blocking call warnings

**Example Usage**:
```python
from open_helper import async_open_freebox

api = Freepybox(app_desc, token_file)
await async_open_freebox(hass, api, host, port)
# api is now initialized and ready for use
```

#### `router.py` - Router Management
**Description**: Manages Freebox router connection and data synchronization

**Key Class**: `FreeboxRouter`

**Key Methods**:
- `update_all()` - Periodic data synchronization
- `update_device_trackers()` - Update connected devices
- `update_sensors()` - Update sensor readings
- `update_home_devices()` - Update home automation devices
- `close()` - Clean connection shutdown

**Signals**:
- `{domain}-{host}-device-new` - New device connected
- `{domain}-{host}-device-update` - Device list updated
- `{domain}-{host}-sensor-update` - Sensor data updated
- `{domain}-{host}-home-device-new` - New home device
- `{domain}-{host}-home-device-update` - Home device updated

**Example Usage**:
```python
from router import FreeboxRouter

router = FreeboxRouter(hass, entry, api, freebox_config)
await router.update_all()
```

#### `config_flow.py` - Configuration Management
**Description**: User-facing configuration flow

**Key Class**: `FreeboxFlowHandler`

**Key Methods**:
- `async_step_user()` - Manual device configuration
- `async_step_link()` - Device authentication
- `async_step_permissions()` - Permission verification
- `async_step_zeroconf()` - Automatic device discovery

**Example Usage**:
```python
# Automatically called by Home Assistant when user adds integration
# Users will see configuration flow in UI
```

#### `entity.py` - Base Entity Class
**Description**: Common functionality for all Freebox entities

**Key Class**: `FreeboxHomeEntity`

**Features**:
- Device registry integration
- State update signals
- Entity lifecycle management
- Attribute handling

#### Platform Modules
- `device_tracker.py` - Connected device tracking
- `sensor.py` - System and connection sensors
- `switch.py` - WiFi and settings switches
- `cover.py` - Blind automation
- `binary_sensor.py` - Status sensors
- `button.py` - Device actions
- `alarm_control_panel.py` - Security system

## Configuration

### Config Entry Format
```python
{
    CONF_HOST: "192.168.1.1",  # Freebox router IP/hostname
    CONF_PORT: 443              # Freebox HTTPS port
}
```

### Discovery Methods
1. **Zeroconf**: Automatic discovery via mDNS (`_fbx-api._tcp.local.`)
2. **Manual**: User-provided host and port
3. **YAML** (Deprecated): Configuration from configuration.yaml

## Error Handling

### Exception Hierarchy
```
HttpRequestError
    ├─ Connection errors
    ├─ Authentication errors
    └─ API errors

InvalidTokenError
    └─ Application descriptor validation failed

AuthorizationError
    ├─ User denied authorization
    └─ Authorization timeout

ConfigEntryNotReady
    └─ Transient errors (retry later)
```

### Logging Levels
- **ERROR**: Integration failures, connection errors
- **WARNING**: Permission issues, unsupported features
- **INFO**: Successful initialization, significant events
- **DEBUG**: Connection details, sensor updates, token operations

## Data Flow

### Initialization Sequence
```
1. User adds integration via UI
2. async_setup_entry() called
3. get_api() creates Freepybox instance
4. async_open_freebox() initializes connection
5. First-time auth: User presses Freebox button
6. Token saved locally
7. FreeboxRouter created and initial update performed
8. Platforms forwarded for entity setup
9. Periodic updates scheduled
```

### Update Cycle
```
Every 30 seconds (SCAN_INTERVAL):
1. update_device_trackers() - Get connected devices
2. update_sensors() - Get system/connection stats
3. update_home_devices() - Get home automation devices
4. Signals dispatched to entities
5. Entities update their state
```

## Security Considerations

### Token Storage
- Tokens stored in Home Assistant storage directory
- Per-host token files: `{slugified_host}.conf`
- File permissions set by Home Assistant
- Never logged or transmitted unnecessarily

### SSL/TLS
- Uses Freebox certificate bundle
- Self-signed certificate support
- Strict validation disabled (Freebox limitation)

### Authentication
- Token-based authentication with Freebox API
- No username/password storage
- First-time authorization requires user confirmation on device

## Performance Characteristics

### Update Cycle Timing
- Poll interval: 30 seconds (configurable)
- Typical update time: 0.5-2 seconds
- Network latency: Depends on network connection

### Memory Usage
- Per-integration: ~5-10 MB
- Device caching: ~1 KB per device/sensor
- Token file: ~500 bytes

### Event Loop Blocking
- **Before fix**: ~100-500ms blocking calls per update
- **After fix**: 0ms blocking calls (all offloaded to executor)

## Troubleshooting

### Common Issues

#### "Failed to connect to Freebox"
- Check host/port are correct
- Ensure Freebox is accessible from Home Assistant
- Verify network connectivity

#### "Authorization failed"
- User must press button on Freebox device
- Check Home Assistant logs for permission requirements
- Verify Freebox Home permissions are enabled

#### "Blocking call warnings"
- Only occurs on Python 3.13+
- Update to latest integration version (≥1.1.68)
- Check async_open_freebox() is being used

#### "No entities appearing"
- Verify permissions for each entity type
- Check logs for "permission not granted"
- Ensure platforms are listed in PLATFORMS constant

## Development Guide

### Adding New Entity Types
1. Create new `xxx.py` platform file
2. Extend `entity.FreeboxHomeEntity` or `entity.Entity`
3. Implement required Home Assistant methods
4. Add to `const.PLATFORMS`
5. Update Doxygen documentation

### Testing Changes
1. Restart Home Assistant
2. Check logs for errors
3. Verify entity discovery
4. Test entity state updates

### Doxygen Documentation
Generate documentation:
```bash
cd /config/custom_components/freebox_home
chmod +x generate_docs.sh
./generate_docs.sh --html --open
```

Documentation output: `docs/html/index.html`

## API References

### Upstream Libraries
- [freebox_api](https://github.com/hacf-fr/freebox_api) - Freebox API wrapper
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client
- [Home Assistant Core](https://developers.home-assistant.io/) - Home Assistant framework

### External Resources
- [Freebox API Documentation](https://dev.freebox.fr/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

## Version History

### v1.1.68 (Current)
- ✓ Fixed Python 3.13+ blocking call warnings
- ✓ Improved error logging with context
- ✓ Fixed connection resource leaks
- ✓ Enhanced Doxygen documentation
- ✓ Code quality improvements

### v1.1.0 - v1.1.67
- Previous development iterations
- See CHANGELOG for details

## Contact & Support

- **Repository**: https://github.com/hacf-fr/freebox_home
- **Issue Tracker**: GitHub Issues
- **Home Assistant Forum**: https://community.home-assistant.io/

---

**Generated**: January 17, 2026  
**Integration Version**: 1.1.68  
**Python Version**: 3.11+  
**Home Assistant Version**: 2024.12+

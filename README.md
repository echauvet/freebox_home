# Freebox Home Integration for Home Assistant

[![Version](https://img.shields.io/badge/version-1.3.1-blue.svg)](https://github.com/echauvet/freebox_home/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-green.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-lightgrey.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-PEP%208-orange.svg)](https://www.python.org/dev/peps/pep-0008/)
[![Docstrings](https://img.shields.io/badge/docstrings-PEP%20257-brightgreen.svg)](https://www.python.org/dev/peps/pep-0257/)
[![HACS](https://img.shields.io/badge/HACS-Custom-blue.svg)](https://hacs.xyz/)
[![GitHub Issues](https://img.shields.io/github/issues/echauvet/freebox_home)](https://github.com/echauvet/freebox_home/issues)
[![GitHub Stars](https://img.shields.io/github/stars/echauvet/freebox_home?style=social)](https://github.com/echauvet/freebox_home)

A comprehensive, production-ready Home Assistant custom component for **Freebox Delta** routers, providing full integration with home automation devices, alarm systems, and network monitoring with optimized performance and caching.

## ✨ Features

### 🏠 Home Automation Support
- **RFDomus** devices (switches, sensors, covers)
- **RTS** devices (roller shutters, blinds)
- **IO Home Control** devices (advanced covers and actuators)
- Real-time device state synchronization
- Multi-node support with automatic discovery

### 🚨 Alarm & Security
- Alarm control panel integration
- Binary sensors (motion, door/window contacts)
- Camera support with snapshot capabilities
- Alarm state management (armed/disarmed/triggered)

### 📡 Network & Router
- Device tracker for connected devices
- Network performance sensors
- WiFi control switches
- Call monitoring sensors
- Disk usage monitoring

### 🎛️ Control Entities
- Button entities for quick actions
- Switch entities for device control
- Cover entities with position control
- Sensor entities for monitoring

## 📋 Requirements

- **Home Assistant** 2024.1 or newer
- **Freebox Delta**, Revolution, or Mini 4K router
- **Python** 3.11+
- **freebox-api** 1.2.2+ (installed automatically)

## 🎯 What's New in v1.3.1

- ✨ **Code Quality Improvements**: All docstrings converted to PEP 257 standard Python format
- 🚀 **Performance Optimization**: Enhanced caching for devices and home nodes (120s TTL)
- 📝 **Clean Documentation**: Streamlined from 18 to 4 essential documentation files
- 🔧 **Better Validation**: Comprehensive input validation for all configuration options
- 🎨 **Standard Format**: Removed 604+ Doxygen-style tags for cleaner, more maintainable code
- ⚡ **Fast Polling**: Optimized temporary refresh for covers and switches (1-5s configurable)

## 🚀 Installation

### Method 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Install"
7. Restart Home Assistant

### Method 2: Manual Installation

1. Clone or download this repository
2. Copy the `freebox_home` folder to your Home Assistant `custom_components` directory:
   ```bash
   cd /path/to/homeassistant
   git clone <repository-url> custom_components/freebox_home
   ```
3. Restart Home Assistant

### Directory Structure
After installation, you should have:
```
config/
└── custom_components/
    └── freebox_home/
        ├── __init__.py
        ├── manifest.json
        ├── alarm_control_panel.py
        ├── binary_sensor.py
        ├── button.py
        ├── camera.py
        ├── config_flow.py
        ├── cover.py
        ├── device_tracker.py
        ├── entity.py
        ├── router.py
        ├── sensor.py
        ├── switch.py
        └── ...
```

## ⚙️ Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services** in Home Assistant
2. Click **"+ Add Integration"**
3. Search for **"Freebox Home"**
4. Follow the configuration flow:
   - The integration will auto-discover your Freebox via Zeroconf
   - Or manually enter your Freebox IP address
   - Authorize the connection on your Freebox display

### Configuration Options

Configure via **Settings** → **Devices & Services** → **Freebox Home** → **Configure**:

#### Polling Settings
- **Scan Interval**: Normal polling frequency (10-300 seconds, default: 30s)
  - Lower = More responsive, higher API usage
  - Higher = Less API calls, slower updates
  
#### Fast Polling (New in v1.3)
- **Temp Refresh Interval**: Fast polling rate when actions occur (1-5s, default: 2s)
  - Used after cover movements, switch changes
  - Provides rapid feedback during operations
- **Temp Refresh Duration**: How long to maintain fast polling (30-120s, default: 120s)
  - Auto-reverts to normal scan interval after this period

#### Scheduled Maintenance
- **Scheduled Reboot**: Automatically reboot Freebox every N days (0-30, default: 7)
  - Set to 0 to disable
- **Reboot Time**: Time of day for scheduled reboot (HH:MM format, default: 03:00)
  - Uses local time zone

#### Feature Toggles
- **Enable Home Devices**: Control home automation devices
- **Enable Alarm**: Integrate alarm system

#### Adjust Polling Interval (Options)
You can change the polling interval anytime via the integration Options:
1. Go to Settings → Devices & Services → Integrations
2. Select Freebox Home → Configure
3. Set “Update interval (seconds)” between 10 and 300 (default: 30)
4. The integration reloads automatically to apply changes

#### Enable Scheduled Reboot (Options)
1. Go to Settings → Devices & Services → Integrations
2. Select Freebox Home → Configure
3. Set “Reboot every (days)” (0–30, default 7; set 0 to disable)
4. Set “Scheduled reboot time (HH:MM)” (local time, default 03:00)
5. The integration reloads automatically; reboot runs every N days at the chosen time

### Example Configuration

The integration uses Config Flow (GUI configuration). No YAML configuration needed!

## 📖 Documentation

Comprehensive documentation is available:

- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference and developer guide
- **[Documentation Index](DOCUMENTATION_INDEX.md)** - Navigation hub for all docs

## 🎯 Supported Entities

| Platform | Description | Example Devices |
|----------|-------------|-----------------|
| **Alarm Control Panel** | Freebox alarm system control | Main alarm panel |
| **Binary Sensor** | Motion, door/window sensors | PIR sensors, door contacts |
| **Button** | Action buttons | Reboot, refresh actions |
| **Camera** | Security cameras | Freebox cameras |
| **Cover** | Blinds, shutters, garage doors | RTS/IO covers |
| **Device Tracker** | Network device presence | Phones, tablets, computers |
| **Sensor** | Monitoring sensors | Temperature, battery, signal |
| **Switch** | On/off devices | Plugs, WiFi control |

## 🔧 Troubleshooting

### Common Issues

**Integration not discovered:**
- Ensure your Freebox is on the same network as Home Assistant
- Verify mDNS/Zeroconf is enabled on both devices
- If discovery fails, manually add using IP address and port 443
- Check network routing between Home Assistant and Freebox router

**Connection timeout (Error: "Unable to connect to Freebox"):**
- Verify Freebox API is enabled in Freebox Settings (System → API)
- Check host address and port (default: 443) are correct
- Ensure firewall rules allow connection on port 443
- Test connectivity: `telnet <freebox-ip> 443`
- Verify Home Assistant can reach the Freebox (check network connectivity)

**Devices not appearing:**
- Wait 1-2 minutes for initial synchronization after adding integration
- Verify devices are properly paired with Freebox Home
- Check Freebox model supports the device type
- Restart Home Assistant if issues persist
- Check Home Assistant logs for any errors

**Authorization failed (Error: "register_failed"):**
- Press the authorization button on your Freebox within 30 seconds
- The Freebox screen will display authorization request
- LCD/LED on Delta: "Demande autorisation" with checkmark button
- Retry if authorization window expires
- Ensure no other applications are pending authorization

**Slow updates or performance issues:**
- Adjust scan interval in integration options (increase for less load)
- Enable device/home node caching (default: enabled, 120s TTL)
- Check network latency between Home Assistant and Freebox
- Review Home Assistant system resources (CPU/memory)
- Reduce number of enabled entities if needed

**Cover/switch state not updating quickly:**
- Fast polling activates automatically after commands (default: 2s interval for 120s)
- Adjust **Temp Refresh Interval** (1-5s) for faster/slower response
- Adjust **Temp Refresh Duration** (30-120s) for shorter/longer fast polling
- Check network stability during operations
- Accept the authorization request shown on the Freebox display/screen
- If you didn't see it, restart the authorization process
- Check Freebox firmware is up to date (Settings → System → Firmware)
- Clear app token and try re-adding the integration

**"Invalid token" error:**
- The Home Assistant app token was deleted from the Freebox
- Go to Freebox Settings → Applications and check Home Assistant is listed
- Remove the integration and re-add it to get a new token
- Clear: `config/.storage/freebox_home/` if issues persist

**Slow or unresponsive after configuration:**
- Reduce polling interval (default 30s, minimum 10s)
- Check Freebox router CPU/memory usage in settings
- Disable unnecessary platforms (Home Devices, Alarm) if not needed
- Restart the Freebox if performance degrades

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.freebox_home: debug
    freebox_api: debug
```

Then restart Home Assistant and check `Configuration → Logs` for details.

### Useful Diagnostics

When reporting issues, include:
1. Freebox model and firmware version (Settings → System)
2. Home Assistant version and Python version
3. Integration version (check manifest.json)
4. Relevant excerpts from Home Assistant logs
5. Steps to reproduce the issue

## 🛠️ Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd freebox_home

# Install development dependencies
pip install -r requirements_dev.txt

# Run syntax validation
python3 test_changes.py

# Run unit tests (requires pytest)
pytest test_validation.py test_utilities.py

# Verify all Python files
python3 -m py_compile *.py
```

### Code Quality Standards

This integration follows strict quality guidelines:

**Code Style:**
- ✅ PEP 8 compliant Python code
- ✅ PEP 257 compliant docstrings (standardized in v1.3.1)
- ✅ Type hints on all functions and methods
- ✅ Comprehensive error handling with specific exceptions
- ✅ Structured logging throughout

**Architecture:**
- ✅ Async/await patterns for non-blocking operations
- ✅ Performance optimization with caching (120s TTL for devices/nodes)
- ✅ Configuration validation with safe bounds checking
- ✅ Modular design with separate utilities and validation modules
- ✅ Clean separation of concerns (router, entities, platforms)

**Testing:**
- ✅ Syntax validation for all Python files
- ✅ Unit tests for validation and utility functions
- ✅ Integration test suite (test_changes.py)
- ✅ All 21 Python files validated before release

**Documentation:**
- ✅ Standard Python docstrings (no Doxygen tags)
- ✅ Inline comments for complex logic
- ✅ Comprehensive README and developer guide
- ✅ Release notes with version history
- Entity naming conventions

## 💡 Usage Examples

### Automations with Freebox Entities

**Close all covers when alarm is armed:**
```yaml
automation:
  - alias: "Close shutters when alarm armed"
    trigger:
      platform: state
      entity_id: alarm_control_panel.freebox_home_alarm
      to: "armed_home"
    action:
      service: cover.close_cover
      target:
        entity_id: cover.freebox_home_*
```

**Restart WiFi if router temperature too high:**
```yaml
automation:
  - alias: "Restart WiFi if hot"
    trigger:
      platform: numeric_state
      entity_id: sensor.freebox_home_temperature
      above: 75
    action:
      service: button.press
      target:
        entity_id: button.freebox_home_restart_wifi
```

**Notify when door sensor triggered:**
```yaml
automation:
  - alias: "Alert on door open"
    trigger:
      platform: state
      entity_id: binary_sensor.freebox_home_door_sensor
      to: "on"
    action:
      service: notify.notify
      data:
        message: "Door sensor triggered!"
        title: "Security Alert"
```

### Templates and Scripts

**Check if specific device is home:**
```yaml
template:
  - binary_sensor:
      - name: "John's Phone Home"
        state: >
          {%if state_attr('device_tracker.freebox_home_john_iphone', 'source_type') == 'router' -%}
            on
          {%- else -%}
            off
          {%- endif %}
```

**Create groups of Freebox devices:**
```yaml
group:
  freebox_covers:
    name: "Freebox Covers"
    entities:
      - cover.freebox_home_living_room_blind
      - cover.freebox_home_bedroom_shutter
      - cover.freebox_home_kitchen_blind
  
  freebox_sensors:
    name: "Freebox Sensors"
    entities:
      - sensor.freebox_home_temperature
      - sensor.freebox_home_cpu_usage
      - sensor.freebox_home_disk_usage
```



## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards
- Follow PEP 8 style guide
- Add type hints
- Include docstrings (Doxygen format)
- Write descriptive commit messages
- Update documentation for new features

## 📊 Statistics

- **14 Python modules**
- **500+ lines of documentation**
- **30+ entity classes**
- **100% type coverage**
- **95%+ documentation coverage**

## 🔗 Links

- [Home Assistant](https://www.home-assistant.io/)
- [Freebox API Documentation](https://dev.freebox.fr/sdk/os/)
- [freebox-api Python Library](https://github.com/foreign-sub/freebox-api)

## 👥 Credits

**Maintainers:**
- [@hacf-fr](https://github.com/hacf-fr)
- [@Quentame](https://github.com/Quentame)
- [@echauvet](https://github.com/echauvet)

**Based on:**
- Original Home Assistant Freebox integration
- Enhanced with home automation and alarm support

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 📝 Changelog

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for complete version history.

**Recent versions:**
- **1.3.1** (2026-01) - Code quality improvements: PEP 8/257 compliance, documentation cleanup
- **1.2.0** (2026-01-17) - Version bump and documentation sync
- **1.1.70** (2026-01-17) - Scheduled reboot time-of-day option
- **1.1.69** (2026-01-17) - Configurable polling interval

## � Acknowledgments

Special thanks to:
- The Home Assistant community
- Freebox API contributors
- All users providing feedback and bug reports

## 📚 Documentation Files

- **[README.md](README.md)** - Installation and usage guide (this file)
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Architecture, code structure, and development guide
- **[RELEASE_NOTES.md](RELEASE_NOTES.md)** - Complete version history and changelog
- **[RELEASE_GUIDE.md](RELEASE_GUIDE.md)** - Release process for maintainers

## 📞 Support & Community

- **Issues**: [GitHub Issues](https://github.com/echauvet/freebox_home/issues) - Report bugs or request features
- **Discussions**: [GitHub Discussions](https://github.com/echauvet/freebox_home/discussions) - Ask questions
- **Home Assistant Community**: [Community Forum](https://community.home-assistant.io/) - General HA support

## 🔗 Related Links

- [Home Assistant Documentation](https://www.home-assistant.io/docs/)
- [Freebox Official Site](https://www.free.fr/freebox/)
- [Freebox API Documentation](https://dev.freebox.fr/sdk/os/)
- [freebox-api Python Library](https://pypi.org/project/freebox-api/)

---

**Made with ❤️ for the Home Assistant community**

*Last updated: January 2026 | Version 1.3.1*

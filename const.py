"""Constants and configuration mappings for Freebox integration.

This module defines all constants, enumerations, entity descriptions, and
configuration mappings used throughout the Freebox Home integration.
- DOMAIN: Integration domain identifier
- PLATFORMS: Supported Home Assistant platforms
- API_VERSION: Freebox API version (v6)
- APP_DESC: Application metadata for API authentication

Normal Polling (Standard Intervals):
- CONF_SCAN_INTERVAL: Normal polling interval (10-300 seconds, default 30)
  * Low intervals (10-15s): Faster updates, higher API usage, more responsive
  * Default (30s): Balanced between responsiveness and API efficiency
  * High intervals (60-300s): Lower API usage, delayed updates

Temporary Fast Polling (Quick Response):
- CONF_TEMP_REFRESH_INTERVAL: Fast polling interval (1-5 seconds, default 2)
  * Low intervals (1-2s): Very fast updates when actions are triggered
  * High intervals (3-5s): Fast but slightly more conservative
  * Used for cover position updates and time-sensitive operations
  * Automatically stops after CONF_TEMP_REFRESH_DURATION or when no change detected

- CONF_TEMP_REFRESH_DURATION: Fast polling duration (30-120 seconds, default 60)
  * How long to maintain fast polling after an action
  * Low durations (30s): Brief fast polling, quick revert to normal
  * Default (60s): Balanced responsiveness for 1 minute
  * Note: Enforced maximum 60 seconds regardless of config
  * Auto-stops earlier if no position/state change detected for 20 seconds
  * Each new action resets the timer with fresh state tracking

Other Configuration:
- CONF_REBOOT_INTERVAL_DAYS: Scheduled reboot frequency (0-30 days)
- CONF_REBOOT_TIME: Reboot time in HH:MM format (24-hour, local)
All configuration values are validated within safe operational bounds:

Polling Intervals (10-300 seconds):
- Lower bounds (10s minimum): Prevents excessive API requests
- Upper bounds (300s maximum): Ensures responsive updates
- Affects device tracking, sensor updates, system monitoring
- Configurable per Home Assistant instance

Fast Polling Intervals (1-5 seconds):
- Lower bounds (1s minimum): Rapid response for user interactions
- Upper bounds (5s maximum): Maintains responsiveness without overload
- Triggers on cover position updates, action commands
- Automatically reverts after specified duration
- Short durations preserve API efficiency

Fast Polling Duration (30-120 seconds):
- Lower bounds (30s minimum): Quick revert to normal polling
- Upper bounds (120s maximum): Extended responsive window
- Balances user experience with API load
- Set based on expected operation time

Other Validations:
- Reboot parameters ensure system stability
- Port validation prevents network conflicts
- Time format ensures predictable scheduling
Comprehensive entity descriptions for all supported device types:
- Sensors: Temperature, speed, battery, disk usage
- Binary Sensors: Motion, doors, openings, covers
- Covers: Shutters, openers, blinds
- Cameras: Security and monitoring cameras
- Switches: WiFi, device control
- Alarm: Security system control    See Also:
        FreeboxHomeCategory for device type enumeration    See Also:
        CATEGORY_TO_MODEL for device identification    See Also:
        HOME_NODES_SENSORS, HOME_NODES_BINARY_SENSORS for entity mappings
"""
from __future__ import annotations

import enum
import socket

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.cover import CoverDeviceClass, CoverEntityDescription
from homeassistant.components.camera import CameraEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, PERCENTAGE, Platform
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "freebox_home"
SERVICE_REBOOT = "reboot"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30
CONF_REBOOT_INTERVAL_DAYS = "reboot_interval_days"
DEFAULT_REBOOT_INTERVAL_DAYS = 7
CONF_REBOOT_TIME = "reboot_time"
CONF_TEMP_REFRESH_INTERVAL = "temp_refresh_interval"
DEFAULT_TEMP_REFRESH_INTERVAL = 2
CONF_TEMP_REFRESH_DURATION = "temp_refresh_duration"
DEFAULT_TEMP_REFRESH_DURATION = 60

TEMP_REFRESH_DURATION = 60
TEMP_REFRESH_INTERVAL = 2

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.109",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.COVER,
    Platform.CAMERA,
]

# Home
class FreeboxHomeCategory(str, enum.Enum):
    """Freebox Home device categories.
    
    Enumeration of all supported Freebox Home device categories
    used for device classification and handling.
    """

    ALARM = "alarm"
    CAMERA = "camera"
    DWS = "dws"
    IOHOME = "iohome"
    KFB = "kfb"
    OPENER = "opener"
    PIR = "pir"
    RTS = "rts"

DEFAULT_DEVICE_NAME = "Unknown device"

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Sensors
CONNECTION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rate_down",
        name="Freebox download speed",
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        icon="mdi:download-network",
    ),
    SensorEntityDescription(
        key="rate_up",
        name="Freebox upload speed",
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        icon="mdi:upload-network",
    ),
)
CONNECTION_SENSORS_KEYS: list[str] = [desc.key for desc in CONNECTION_SENSORS]
CALL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="missed",
        name="Freebox missed calls",
        icon="mdi:phone-missed",
    ),
)
DISK_PARTITION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="partition_free_space",
        name="Free space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
)
HOME_NODE_BATTERY_SENSOR: SensorEntityDescription = SensorEntityDescription(
    key="battery",
    name="Battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=SensorDeviceClass.BATTERY,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
)
HOME_NODE_REMOTE_BUTTON_SENSOR: SensorEntityDescription = SensorEntityDescription(
    key="pushed",
    name="Last action",
)
HOME_NODES_SENSORS: dict[str, SensorEntityDescription] = {
    "battery": HOME_NODE_BATTERY_SENSOR,
    "pushed": HOME_NODE_REMOTE_BUTTON_SENSOR,
}

# Binary Sensors
HOME_NODE_COVER_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="cover",
        name="Cover",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.OPENING,
    )
)
HOME_NODE_MOTION_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
    )
)
HOME_NODE_OPENING_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="opening",
        name="Status",
        device_class=BinarySensorDeviceClass.OPENING,
    )
)
HOME_NODES_BINARY_SENSORS: dict[str, BinarySensorEntityDescription] = {
    "cover": HOME_NODE_COVER_BINARY_SENSOR,
    "opening": HOME_NODE_OPENING_BINARY_SENSOR,
    "motion": HOME_NODE_MOTION_BINARY_SENSOR,
}

# Cover
HOME_NODE_SHUTTER_COVER: CoverEntityDescription = CoverEntityDescription(
    key="shutter",
    name="Shutter",
    device_class=CoverDeviceClass.SHUTTER,
)

# Basic Cover
HOME_NODE_BASIC_SHUTTER_COVER: CoverEntityDescription = CoverEntityDescription(
    key="basic_shutter", name="basic_shutter", device_class=CoverDeviceClass.SHUTTER
)

# Opener
HOME_NODE_OPENER_COVER: CoverEntityDescription = CoverEntityDescription(
    key="opener",
    name="Opener",
    device_class=CoverDeviceClass.WINDOW,
)
HOME_NODES_COVERS: dict[str, CoverEntityDescription] = {
    "shutter": HOME_NODE_SHUTTER_COVER,
    "opener": HOME_NODE_OPENER_COVER,
    "basic_shutter": HOME_NODE_BASIC_SHUTTER_COVER,
}

# Camera
HOME_NODE_CAMERA: CameraEntityDescription = CameraEntityDescription(
    key=FreeboxHomeCategory.CAMERA, name=FreeboxHomeCategory.CAMERA
)

# Alarm
HOME_NODES_ALARM_REMOTE_KEY: list[str] = [
    "Alarm 1 ON",
    "Alarm OFF",
    "Alarm 2 ON",
    "Not used",
]


# Icons
DEVICE_ICONS = {
    "freebox_delta": "mdi:television-guide",
    "freebox_hd": "mdi:television-guide",
    "freebox_mini": "mdi:television-guide",
    "freebox_player": "mdi:television-guide",
    "ip_camera": "mdi:cctv",
    "ip_phone": "mdi:phone-voip",
    "laptop": "mdi:laptop",
    "multimedia_device": "mdi:play-network",
    "nas": "mdi:nas",
    "networking_device": "mdi:network",
    "printer": "mdi:printer",
    "router": "mdi:router-wireless",
    "smartphone": "mdi:cellphone",
    "tablet": "mdi:tablet",
    "television": "mdi:television",
    "vg_console": "mdi:gamepad-variant",
    "workstation": "mdi:desktop-tower-monitor",
}


ATTR_DETECTION = "detection"

CATEGORY_TO_MODEL = {
    FreeboxHomeCategory.PIR: "F-HAPIR01A",
    FreeboxHomeCategory.CAMERA: "F-HACAM01A",
    FreeboxHomeCategory.DWS: "F-HADWS01A",
    FreeboxHomeCategory.KFB: "F-HAKFB01A",
    FreeboxHomeCategory.ALARM: "F-MSEC07A",
    FreeboxHomeCategory.RTS: "RTS",
    FreeboxHomeCategory.IOHOME: "IOHome",
}
HOME_COMPATIBLE_CATEGORIES = [
    FreeboxHomeCategory.ALARM,
    FreeboxHomeCategory.CAMERA,
    FreeboxHomeCategory.DWS,
    FreeboxHomeCategory.IOHOME,
    FreeboxHomeCategory.KFB,
    FreeboxHomeCategory.PIR,
    FreeboxHomeCategory.RTS,
]

"""
@file const.py
@author Freebox Home Contributors
@brief Freebox component constants and configurations.
@version 1.2.0.1

This module defines all constants, enumerations, entity descriptions, and
configuration mappings used throughout the Freebox Home integration.
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

DOMAIN = "freebox_home"  ##< Integration domain identifier
SERVICE_REBOOT = "reboot"  ##< Reboot service identifier

## Configuration keys
CONF_SCAN_INTERVAL = "scan_interval"  ##< Scan interval configuration key
DEFAULT_SCAN_INTERVAL = 30  ##< Default scan interval in seconds
CONF_REBOOT_INTERVAL_DAYS = "reboot_interval_days"  ##< Scheduled reboot interval in days
DEFAULT_REBOOT_INTERVAL_DAYS = 7  ##< Default: every 7 days
CONF_REBOOT_TIME = "reboot_time"  ##< Scheduled reboot time of day (HH:MM, local time)
CONF_TEMP_REFRESH_INTERVAL = "temp_refresh_interval"  ##< Temporary refresh polling interval in seconds
DEFAULT_TEMP_REFRESH_INTERVAL = 2  ##< Default: poll every 2 seconds during temp refresh
CONF_TEMP_REFRESH_DURATION = "temp_refresh_duration"  ##< Temporary refresh duration in seconds
DEFAULT_TEMP_REFRESH_DURATION = 120  ##< Default: fast poll for 120 seconds

## Temporary refresh configuration for cover position updates
TEMP_REFRESH_DURATION = 120  ##< Duration of increased refresh frequency in seconds (deprecated, use config)
TEMP_REFRESH_INTERVAL = 2  ##< Interval between refreshes during temporary period in seconds (deprecated, use config)

##< Application description for Freebox API authentication
APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.109",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"  ##< Freebox API version to use

##< Platforms supported by this integration
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
    """
    @brief Freebox Home device categories.
    
    Enumeration of all supported Freebox Home device categories
    used for device classification and handling.
    """

    ALARM = "alarm"      ##< Alarm system devices
    CAMERA = "camera"    ##< Camera devices
    DWS = "dws"          ##< Door/Window sensors
    IOHOME = "iohome"    ##< IO Home Control devices
    KFB = "kfb"          ##< Key fob devices
    OPENER = "opener"    ##< Door/gate opener devices
    PIR = "pir"          ##< Passive Infrared motion sensors
    RTS = "rts"          ##< RTS protocol devices

DEFAULT_DEVICE_NAME = "Unknown device"  ##< Default name for unidentified devices

# to store the cookie
STORAGE_KEY = DOMAIN  ##< Storage key for authentication token
STORAGE_VERSION = 1  ##< Storage version for authentication token

# Sensors
##< Connection speed sensor descriptions
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
CONNECTION_SENSORS_KEYS: list[str] = [desc.key for desc in CONNECTION_SENSORS]  ##< List of connection sensor keys

##< Call-related sensor descriptions
CALL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="missed",
        name="Freebox missed calls",
        icon="mdi:phone-missed",
    ),
)

##< Disk partition sensor descriptions
DISK_PARTITION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="partition_free_space",
        name="Free space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
)

##< Battery sensor description for Home nodes
HOME_NODE_BATTERY_SENSOR: SensorEntityDescription = SensorEntityDescription(
    key="battery",
    name="Battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=SensorDeviceClass.BATTERY,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
)

##< Remote button action sensor description for Home nodes
HOME_NODE_REMOTE_BUTTON_SENSOR: SensorEntityDescription = SensorEntityDescription(
    key="pushed",
    name="Last action",
)

##< Mapping of Home node sensor types to their descriptions
HOME_NODES_SENSORS: dict[str, SensorEntityDescription] = {
    "battery": HOME_NODE_BATTERY_SENSOR,
    "pushed": HOME_NODE_REMOTE_BUTTON_SENSOR,
}

# Binary Sensors
##< Cover binary sensor description for Home nodes
HOME_NODE_COVER_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="cover",
        name="Cover",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.OPENING,
    )
)

##< Motion binary sensor description for Home nodes
HOME_NODE_MOTION_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
    )
)

##< Opening binary sensor description for Home nodes (door/window status)
HOME_NODE_OPENING_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="opening",
        name="Status",
        device_class=BinarySensorDeviceClass.OPENING,
    )
)

##< Mapping of Home node binary sensor types to their descriptions
HOME_NODES_BINARY_SENSORS: dict[str, BinarySensorEntityDescription] = {
    "cover": HOME_NODE_COVER_BINARY_SENSOR,
    "opening": HOME_NODE_OPENING_BINARY_SENSOR,
    "motion": HOME_NODE_MOTION_BINARY_SENSOR,
}

# Cover
##< Shutter cover description for Home nodes
HOME_NODE_SHUTTER_COVER: CoverEntityDescription = CoverEntityDescription(
    key="shutter",
    name="Shutter",
    device_class=CoverDeviceClass.SHUTTER,
)

# Basic Cover
##< Basic shutter cover description for simple Home node covers
HOME_NODE_BASIC_SHUTTER_COVER: CoverEntityDescription = CoverEntityDescription(
    key="basic_shutter", name="basic_shutter", device_class=CoverDeviceClass.SHUTTER
)

# Opener
##< Opener cover description for door/gate opener Home nodes
HOME_NODE_OPENER_COVER: CoverEntityDescription = CoverEntityDescription(
    key="opener",
    name="Opener",
    device_class=CoverDeviceClass.WINDOW,
)

##< Mapping of Home node cover types to their descriptions
HOME_NODES_COVERS: dict[str, CoverEntityDescription] = {
    "shutter": HOME_NODE_SHUTTER_COVER,
    "opener": HOME_NODE_OPENER_COVER,
    "basic_shutter": HOME_NODE_BASIC_SHUTTER_COVER,
}

# Camera
##< Camera entity description for Home node cameras
HOME_NODE_CAMERA: CameraEntityDescription = CameraEntityDescription(
    key=FreeboxHomeCategory.CAMERA, name=FreeboxHomeCategory.CAMERA
)

# Alarm
##< Alarm remote key button labels
HOME_NODES_ALARM_REMOTE_KEY: list[str] = [
    "Alarm 1 ON",
    "Alarm OFF",
    "Alarm 2 ON",
    "Not used",
]


# Icons
##< Mapping of device types to Material Design Icons
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


ATTR_DETECTION = "detection"  ##< Detection attribute key

##< Mapping from Freebox Home categories to device model identifiers
CATEGORY_TO_MODEL = {
    FreeboxHomeCategory.PIR: "F-HAPIR01A",
    FreeboxHomeCategory.CAMERA: "F-HACAM01A",
    FreeboxHomeCategory.DWS: "F-HADWS01A",
    FreeboxHomeCategory.KFB: "F-HAKFB01A",
    FreeboxHomeCategory.ALARM: "F-MSEC07A",
    FreeboxHomeCategory.RTS: "RTS",
    FreeboxHomeCategory.IOHOME: "IOHome",
}

##< List of Freebox Home categories that support home automation features
HOME_COMPATIBLE_CATEGORIES = [
    FreeboxHomeCategory.ALARM,
    FreeboxHomeCategory.CAMERA,
    FreeboxHomeCategory.DWS,
    FreeboxHomeCategory.IOHOME,
    FreeboxHomeCategory.KFB,
    FreeboxHomeCategory.PIR,
    FreeboxHomeCategory.RTS,
]
""""""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from homeassistant.components.camera import DEFAULT_CONTENT_TYPE
from homeassistant.components.generic.camera import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_NAME,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    CONF_VERIFY_SSL,
    GenericCamera,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_TO_MODEL, DOMAIN, FreeboxHomeCategory
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox camera entities from a config entry.
    
    Creates and registers camera entities for Freebox Home devices
    that have camera capability.
    
    HOW IT WORKS:
    Scans all Freebox Home devices and creates a camera entity for
    each device with the "camera" category.
        Args:
            hass: Home Assistant instance coordinating the integration
        Args:
            entry: Config entry providing router runtime data
        Args:
            async_add_entities: Callback used to register entities with HA
        Returns:
            None
        See Also:
            FreeboxHomeNodeCamera
    """
    router: FreeboxRouter = entry.runtime_data
    entities = []

    _LOGGER.debug(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )
    
    # Find all camera devices
    for home_node in router.home_nodes.values():
        if home_node["category"] == FreeboxHomeCategory.CAMERA:
            entities.append(
                FreeboxHomeNodeCamera(
                    hass,
                    router,
                    home_node,
                )
            )

    async_add_entities(entities, True)


class FreeBoxCamera(GenericCamera):
    """ Representation of a Freebox camera entity.
    
    This class extends GenericCamera to provide camera functionality
    for Freebox devices with streaming and snapshot capabilities.
    """

    def __init__(self, hass, router, home_node):
        """ Initialize a Freebox camera entity.
        
        Sets up camera configuration including stream and snapshot URLs
        using credentials from the Freebox device properties.
        
        URL ENCODING EXPLAINED:
        Camera passwords might contain special characters like:
        - / (slash) which normally separates URL parts
        - @ (at) which normally separates user from host
        - : (colon) which normally separates user from password
        
        We use urllib.parse.quote() to encode these safely:
        - "/" becomes "%2F"
        - "@" becomes "%40"
        - ":" becomes "%3A"
        
        This ensures the URL works correctly even with special passwords.
        Args:
            hass: Home Assistant instance orchestrating updates
        Args:
            router: FreeboxRouter instance managing API access
        Args:
            home_node: Mapping containing Freebox Home node data
        Returns:
            None
        """
        # Extract camera properties from the device
        props = home_node["props"]
        
        # URL-encode credentials to handle special characters safely
        # safe="" means encode everything except alphanumeric characters
        login = quote(props.get("Login", ""), safe="")
        password = quote(props.get("Pass", ""), safe="")
        ip = props.get("Ip", "")
        
        # Build camera configuration for Home Assistant
        config = {
            CONF_NAME: FreeboxHomeCategory.CAMERA,
            # Live stream URL (HLS format - .m3u8)
            CONF_STREAM_SOURCE: f"http://{login}:{password}@{ip}/img/stream.m3u8",
            # Snapshot URL (size=4 is highest quality)
            CONF_STILL_IMAGE_URL: f"http://{login}:{password}@{ip}/img/snapshot.cgi?size=4&quality=1",
            CONF_VERIFY_SSL: True,
            CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
            CONF_FRAMERATE: 2,  # 2 frames per second for snapshots
            CONF_CONTENT_TYPE: DEFAULT_CONTENT_TYPE,
        }
        
        # Store references for later use
        self._router = router
        self._home_node = home_node
        self._attr_unique_id = f"{router.mac} camera {home_node['id']}"
        
        # Initialize the parent GenericCamera with our configuration
        super().__init__(hass, config, self._attr_unique_id, FreeboxHomeCategory.CAMERA)

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information for this camera.
        Returns:
            DeviceInfo object containing device details
        """
        return self._router.device_info


class FreeboxHomeNodeCamera(FreeBoxCamera):
    """ Representation of a Freebox Home node camera entity.
    
    This class extends FreeBoxCamera with specific handling for
    Freebox Home node cameras, including device information.
    """

    def __init__(
        self,
        hass: Any,
        router: FreeboxRouter,
        home_node: dict[str, Any],
    ) -> None:
        """ Initialize a Freebox Home node camera entity.
        Args:
            hass: Home Assistant instance orchestrating updates
        Args:
            router: FreeboxRouter instance managing API access
        Args:
            home_node: Mapping containing Freebox Home node data
        Returns:
            None
        """
        super().__init__(hass, router, home_node)
        self._home_node = home_node
        self._attr_name = f"{home_node['label']}"
        self._unique_id = f"{self._router.mac} camera {self._home_node['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information for this Home node camera.
        
        Extracts firmware version from node properties if available.
        Returns:
            DeviceInfo object containing device details including firmware version
        """
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=CATEGORY_TO_MODEL.get(self._home_node["category"]),
            name=f"{self._home_node['label']}",
            sw_version=fw_version,
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            manufacturer="Freebox SAS",
        )

""""""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import (
    CALL_SENSORS,
    CONNECTION_SENSORS,
    DISK_PARTITION_SENSORS,
    DOMAIN,
    HOME_NODES_ALARM_REMOTE_KEY,
    HOME_NODES_SENSORS,
)
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)  ##< Logger instance for this module


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """ Set up Freebox sensor entities from a config entry.
    
    Creates and registers various sensor entities including temperature sensors,
    connection sensors, call sensors, disk sensors, and home node sensors.
        Args:
            hass: Home Assistant instance coordinating the integration
        Args:
            entry: Config entry providing router runtime data
        Args:
            async_add_entities: Callback used to register entities with HA
        Returns:
            None
        See Also:
            FreeboxSensor
    """
    router: FreeboxRouter = entry.runtime_data
    entities = []

    _LOGGER.debug(
        "%s - %s - %s temperature sensors",
        router.name,
        router.mac,
        len(router.sensors_temperature),
    )
    entities = [
        FreeboxSensor(
            router,
            SensorEntityDescription(
                key=sensor_name,
                name=f"Freebox {sensor_name}",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            router.mac,
        )
        for sensor_name in router.sensors_temperature
    ]

    entities.extend(
        [
            FreeboxSensor(router, description, router.mac)
            for description in CONNECTION_SENSORS
        ]
    )
    entities.extend(
        [FreeboxCallSensor(router, description) for description in CALL_SENSORS]
    )

    _LOGGER.info("%s - %s - %s disk(s)", router.name, router.mac, len(router.disks))
    entities.extend(
        FreeboxDiskSensor(router, disk, partition, description)
        for disk in router.disks.values()
        for partition in disk["partitions"]
        for description in DISK_PARTITION_SENSORS
    )

    _LOGGER.info(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        for endpoint in home_node.get("show_endpoints"):
            if (
                endpoint["ep_type"] == "signal"
                and endpoint["name"] in HOME_NODES_SENSORS.keys()
            ):
                entities.append(
                    FreeboxHomeNodeSensor(
                        router,
                        home_node,
                        endpoint,
                        HOME_NODES_SENSORS[endpoint["name"]],
                    )
                )

    async_add_entities(entities, True)


class FreeboxSensor(SensorEntity):
    """ Representation of a Freebox sensor.
    
    Base class for all Freebox sensor entities. Handles state updates
    via dispatcher signals rather than polling.
    """

    _attr_should_poll = False  ##< Disable polling, use push updates instead

    def __init__(
        self, router: FreeboxRouter, description: SensorEntityDescription, unik: Any
    ) -> None:
        """ Initialize a Freebox sensor.
        Args:
            router: FreeboxRouter instance managing the connection
        Args:
            description: Entity description containing sensor metadata
        Args:
            unik: Unique identifier for this sensor instance
        Returns:
            None
        """
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """ Update the Freebox sensor state.

        Retrieves the current sensor value from the router and converts
        data rate values from bytes/s to kilobytes/s when appropriate.
        Returns:
            None
        """
        state = self._router.sensors[self.entity_description.key]
        if self.native_unit_of_measurement == UnitOfDataRate.KILOBYTES_PER_SECOND:
            self._attr_native_value = round(state / 1000, 2)
        else:
            self._attr_native_value = state

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information.
        Returns:
            DeviceInfo object containing router device information
        """
        return self._router.device_info

    @callback
    def async_on_demand_update(self) -> None:
        """ Update state on demand.

        Called when a dispatcher signal is received. Updates the sensor
        state and writes it to Home Assistant.
        Returns:
            None
        """
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback.
        
        Called when the entity is added to Home Assistant. Performs initial
        state update and registers for dispatcher signals.
        Returns:
            None
        """
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )


class FreeboxCallSensor(FreeboxSensor):
    """ Representation of a Freebox call sensor.
    
    Tracks phone call events (missed, received, outgoing) and provides
    call history as extra state attributes.
    """

    def __init__(
        self, router: FreeboxRouter, description: SensorEntityDescription
    ) -> None:
        """ Initialize a Freebox call sensor.
        Args:
            router: FreeboxRouter instance managing the connection
        Args:
            description: Entity description containing sensor metadata
        Returns:
            None
        """
        super().__init__(router, description, router.mac)
        self._call_list_for_type: list[dict[str, Any]] = []  ##< List of calls matching this sensor's type

    @callback
    def async_update_state(self) -> None:
        """ Update the Freebox call sensor state.

        Filters the call list for new calls matching this sensor's type
        and updates the count accordingly.
        Returns:
            None
        """
        self._call_list_for_type = []
        if self._router.call_list:
            for call in self._router.call_list:
                if not call["new"]:
                    continue
                if self.entity_description.key == call["type"]:
                    self._call_list_for_type.append(call)

        self._attr_native_value = len(self._call_list_for_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """ Return device specific state attributes.
        
        Provides call history with timestamps as ISO format strings and
        caller names as values.
        Returns:
            Dictionary mapping ISO timestamp strings to caller names
        """
        return {
            dt_util.utc_from_timestamp(call["datetime"]).isoformat(): call["name"]
            for call in self._call_list_for_type
        }


class FreeboxDiskSensor(FreeboxSensor):
    """ Representation of a Freebox disk sensor.
    
    Monitors disk partition usage and reports free space percentage.
    """

    def __init__(
        self,
        router: FreeboxRouter,
        disk: dict[str, Any],
        partition: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """ Initialize a Freebox disk sensor.
        Args:
            router: FreeboxRouter instance managing the connection
        Args:
            disk: Mapping containing disk metadata
        Args:
            partition: Mapping containing partition information
        Args:
            description: Entity description containing sensor metadata
        Returns:
            None
        """
        super().__init__(router, description, f"{disk['id']} {partition['id']}")
        self._disk = disk
        self._partition = partition
        self._attr_name = f"{partition['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._disk['id']} {self._partition['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information.

        Provides device information specific to the disk, including model,
        firmware version, and connection to the router.
        Returns:
            DeviceInfo object containing disk device information
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self._disk["id"])},
            model=self._disk["model"],
            name=f"Disk {self._disk['id']}",
            sw_version=self._disk["firmware"],
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> None:
        """ Update the Freebox disk sensor state.

        Calculates the free space percentage for the partition by
        comparing free bytes to total bytes.
        Returns:
            None
        """
        value = None
        current_disk = self._router.disks.get(self._disk.get("id"))
        for partition in current_disk["partitions"]:
            if self._partition["id"] == partition["id"]:
                value = round(
                    partition["free_bytes"] * 100 / partition["total_bytes"], 2
                )
        self._attr_native_value = value


class FreeboxHomeNodeSensor(FreeboxSensor):
    """ Representation of a Freebox Home node sensor.
    
    Monitors Freebox Home automation nodes and their endpoints,
    such as alarm remotes and various sensors.
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """ Initialize a Freebox Home node sensor.
        Args:
            router: FreeboxRouter instance managing the connection
        Args:
            home_node: Mapping containing home node information
        Args:
            endpoint: Mapping containing endpoint information
        Args:
            description: Entity description containing sensor metadata
        Returns:
            None
        """
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._home_node['id']} {endpoint['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information.

        Provides device information specific to the home node, including
        category, label, firmware version if available, and connection to the router.
        Returns:
            DeviceInfo object containing home node device information
        """
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=f'{self._home_node["category"]}',
            name=f"{self._home_node['label']}",
            sw_version=fw_version,
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> None:
        """ Update the Freebox Home node sensor state.

        Retrieves the current value from the home node endpoint. For button
        push endpoints, translates the button value to a human-readable key name.
        Returns:
            None
        """
        value = None

        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._endpoint["id"] == end_point["id"]:
                    if self._endpoint["name"] == "pushed":
                        if len(end_point.get("history")) > 0:
                            # Get the latest button pushed as pool mode is a mess
                            value = end_point.get("history")[-1].get("value")
                            value = HOME_NODES_ALARM_REMOTE_KEY[int(value) - 1]
                    else:
                        value = end_point["value"]
                    break

        self._attr_native_value = value

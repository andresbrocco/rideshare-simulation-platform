"""Unified facade for managing all agent registries."""

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from matching.driver_geospatial_index import DriverGeospatialIndex
    from matching.driver_registry import DriverRegistry
    from matching.matching_server import MatchingServer


class AgentRegistryManager:
    """Unified facade managing all registries for agent coordination.

    This class provides a single interface for managing driver and rider
    agents across multiple registries (agent lookup, spatial index, status registry).
    """

    def __init__(
        self,
        driver_index: "DriverGeospatialIndex",
        driver_registry: "DriverRegistry",
        matching_server: "MatchingServer",
    ):
        self._agents: dict[str, Any] = {}
        self._driver_index = driver_index
        self._driver_registry = driver_registry
        self._matching_server = matching_server

    def register_driver(self, driver: "DriverAgent") -> None:
        """Register a driver agent in all registries.

        Args:
            driver: The DriverAgent to register
        """
        self._agents[driver.driver_id] = driver
        self._matching_server.register_driver(driver)

    def register_rider(self, rider: "RiderAgent") -> None:
        """Register a rider agent in the agents dict.

        Args:
            rider: The RiderAgent to register
        """
        self._agents[rider.rider_id] = rider

    def get_agent(self, agent_id: str) -> Any | None:
        """Look up an agent (driver or rider) by ID.

        Args:
            agent_id: The ID of the agent to look up

        Returns:
            The agent if found, None otherwise
        """
        return self._agents.get(agent_id)

    def get_driver(self, driver_id: str) -> "DriverAgent | None":
        """Look up a driver by ID.

        Args:
            driver_id: The driver ID to look up

        Returns:
            The DriverAgent if found, None otherwise
        """
        agent = self._agents.get(driver_id)
        if agent and hasattr(agent, "driver_id"):
            return agent
        return None

    def get_rider(self, rider_id: str) -> "RiderAgent | None":
        """Look up a rider by ID.

        Args:
            rider_id: The rider ID to look up

        Returns:
            The RiderAgent if found, None otherwise
        """
        agent = self._agents.get(rider_id)
        if agent and hasattr(agent, "rider_id"):
            return agent
        return None

    def driver_went_online(
        self,
        driver_id: str,
        location: tuple[float, float],
        zone_id: str | None,
    ) -> None:
        """Update registries when a driver goes online.

        Args:
            driver_id: The driver's ID
            location: The driver's current location (lat, lon)
            zone_id: The zone the driver is in (optional)
        """
        lat, lon = location
        logger.info(f"Driver {driver_id} going online at ({lat}, {lon}), zone={zone_id}")
        self._driver_index.add_driver(driver_id, lat, lon, "online")
        logger.info(f"Driver index now has {len(self._driver_index._driver_locations)} drivers")
        self._driver_registry.register_driver(
            driver_id=driver_id,
            status="online",
            zone_id=zone_id,
            location=location,
        )

    def driver_went_offline(self, driver_id: str) -> None:
        """Update registries when a driver goes offline.

        Args:
            driver_id: The driver's ID
        """
        self._driver_index.remove_driver(driver_id)
        self._driver_registry.update_driver_status(driver_id, "offline")

    def driver_location_updated(
        self,
        driver_id: str,
        location: tuple[float, float],
        zone_id: str | None,
    ) -> None:
        """Update driver location across all registries.

        Args:
            driver_id: The driver's ID
            location: The new location (lat, lon)
            zone_id: The zone the driver is in (optional)
        """
        lat, lon = location
        self._driver_index.update_driver_location(driver_id, lat, lon)
        self._driver_registry.update_driver_location(driver_id, location)
        if zone_id:
            self._driver_registry.update_driver_zone(driver_id, zone_id)

    def driver_status_changed(self, driver_id: str, status: str) -> None:
        """Sync driver status across all registries.

        Args:
            driver_id: The driver's ID
            status: The new status
        """
        self._driver_index.update_driver_status(driver_id, status)
        self._driver_registry.update_driver_status(driver_id, status)

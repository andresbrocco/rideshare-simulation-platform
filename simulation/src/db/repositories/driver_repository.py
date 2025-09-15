"""Driver repository for CRUD operations."""

from agents.dna import DriverDNA

from ..schema import Driver
from .base_agent_repository import BaseAgentRepository


class DriverRepository(BaseAgentRepository[Driver, DriverDNA]):
    """Repository for driver CRUD operations."""

    model_class = Driver

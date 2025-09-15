"""Rider repository for CRUD operations."""

from agents.dna import RiderDNA

from ..schema import Rider
from .base_agent_repository import BaseAgentRepository


class RiderRepository(BaseAgentRepository[Rider, RiderDNA]):
    """Repository for rider CRUD operations."""

    model_class = Rider

"""Base repository for agent CRUD operations using generics."""

from typing import Any, ClassVar, Generic, Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..schema import Base


class HasHomeLocation(Protocol):
    """Protocol for DNA types that have a home_location attribute."""

    home_location: tuple[float, float]

    def model_dump_json(self) -> str: ...


ModelT = TypeVar("ModelT", bound=Base)
DNAT = TypeVar("DNAT", bound=HasHomeLocation)


class BaseAgentRepository(Generic[ModelT, DNAT]):
    """Generic base repository for Driver and Rider CRUD operations."""

    model_class: ClassVar[type[Any]]

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, agent_id: str, dna: DNAT) -> None:
        lat, lon = dna.home_location
        agent = self.model_class(
            id=agent_id,
            dna_json=dna.model_dump_json(),
            current_location=f"{lat},{lon}",
            status="offline",
        )
        self.session.add(agent)

    def get(self, agent_id: str) -> ModelT | None:
        return self.session.get(self.model_class, agent_id)

    def update_location(self, agent_id: str, location: tuple[float, float]) -> None:
        agent = self.session.get(self.model_class, agent_id)
        if agent:
            lat, lon = location
            agent.current_location = f"{lat},{lon}"

    def update_status(self, agent_id: str, status: str) -> None:
        agent = self.session.get(self.model_class, agent_id)
        if agent:
            agent.status = status

    def update_rating(
        self, agent_id: str, new_rating: float, rating_count: int
    ) -> None:
        agent = self.session.get(self.model_class, agent_id)
        if agent:
            agent.current_rating = new_rating
            agent.rating_count = rating_count

    def update_active_trip(self, agent_id: str, trip_id: str | None) -> None:
        agent = self.session.get(self.model_class, agent_id)
        if agent:
            agent.active_trip = trip_id

    def batch_create(self, agents: list[tuple[str, DNAT]]) -> None:
        agent_objects = []
        for agent_id, dna in agents:
            lat, lon = dna.home_location
            agent = self.model_class(
                id=agent_id,
                dna_json=dna.model_dump_json(),
                current_location=f"{lat},{lon}",
                status="offline",
            )
            agent_objects.append(agent)
        self.session.add_all(agent_objects)

    def batch_upsert_with_state(self, agents: list[dict[str, Any]]) -> None:
        """Upsert agents with full runtime state for checkpoint.

        Each dict should have: id, dna, location, status, active_trip, rating, rating_count

        Uses a savepoint to ensure the delete+insert is atomic. If any part fails,
        the entire operation rolls back to preserve existing data.
        """
        from sqlalchemy import delete

        from ..transaction import savepoint

        with savepoint(self.session):
            # Delete existing agents and insert fresh (simpler than upsert for SQLite)
            self.session.execute(delete(self.model_class))

            agent_objects = []
            for agent_data in agents:
                dna = agent_data["dna"]
                lat, lon = agent_data["location"]
                agent = self.model_class(
                    id=agent_data["id"],
                    dna_json=dna.model_dump_json(),
                    current_location=f"{lat},{lon}",
                    status=agent_data["status"],
                    active_trip=agent_data.get("active_trip"),
                    current_rating=agent_data.get("rating", 5.0),
                    rating_count=agent_data.get("rating_count", 0),
                )
                agent_objects.append(agent)
            self.session.add_all(agent_objects)

    def list_by_status(self, status: str) -> list[ModelT]:
        stmt = select(self.model_class).where(self.model_class.status == status)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

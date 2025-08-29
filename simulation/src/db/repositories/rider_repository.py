"""Rider repository for CRUD operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.dna import RiderDNA

from ..schema import Rider


class RiderRepository:
    """Repository for rider CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, rider_id: str, dna: RiderDNA) -> None:
        """Create a new rider."""
        lat, lon = dna.home_location
        rider = Rider(
            id=rider_id,
            dna_json=dna.model_dump_json(),
            current_location=f"{lat},{lon}",
            status="idle",
        )
        self.session.add(rider)

    def get(self, rider_id: str) -> Rider | None:
        """Get rider by ID."""
        return self.session.get(Rider, rider_id)

    def update_location(self, rider_id: str, location: tuple[float, float]) -> None:
        """Update rider location."""
        rider = self.session.get(Rider, rider_id)
        if rider:
            lat, lon = location
            rider.current_location = f"{lat},{lon}"

    def update_status(self, rider_id: str, status: str) -> None:
        """Update rider status."""
        rider = self.session.get(Rider, rider_id)
        if rider:
            rider.status = status

    def update_rating(self, rider_id: str, new_rating: float, rating_count: int) -> None:
        """Update rider rating."""
        rider = self.session.get(Rider, rider_id)
        if rider:
            rider.current_rating = new_rating
            rider.rating_count = rating_count

    def update_active_trip(self, rider_id: str, trip_id: str | None) -> None:
        """Update rider active trip."""
        rider = self.session.get(Rider, rider_id)
        if rider:
            rider.active_trip = trip_id

    def batch_create(self, riders: list[tuple[str, RiderDNA]]) -> None:
        """Create multiple riders at once."""
        rider_objects = []
        for rider_id, dna in riders:
            lat, lon = dna.home_location
            rider = Rider(
                id=rider_id,
                dna_json=dna.model_dump_json(),
                current_location=f"{lat},{lon}",
                status="idle",
            )
            rider_objects.append(rider)
        self.session.add_all(rider_objects)

    def list_by_status(self, status: str) -> list[Rider]:
        """List riders by status."""
        stmt = select(Rider).where(Rider.status == status)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

"""Driver repository for CRUD operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.dna import DriverDNA

from ..schema import Driver


class DriverRepository:
    """Repository for driver CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, driver_id: str, dna: DriverDNA) -> None:
        """Create a new driver."""
        lat, lon = dna.home_location
        driver = Driver(
            id=driver_id,
            dna_json=dna.model_dump_json(),
            current_location=f"{lat},{lon}",
            status="offline",
        )
        self.session.add(driver)

    def get(self, driver_id: str) -> Driver | None:
        """Get driver by ID."""
        return self.session.get(Driver, driver_id)

    def update_location(self, driver_id: str, location: tuple[float, float]) -> None:
        """Update driver location."""
        driver = self.session.get(Driver, driver_id)
        if driver:
            lat, lon = location
            driver.current_location = f"{lat},{lon}"

    def update_status(self, driver_id: str, status: str) -> None:
        """Update driver status."""
        driver = self.session.get(Driver, driver_id)
        if driver:
            driver.status = status

    def update_rating(self, driver_id: str, new_rating: float, rating_count: int) -> None:
        """Update driver rating."""
        driver = self.session.get(Driver, driver_id)
        if driver:
            driver.current_rating = new_rating
            driver.rating_count = rating_count

    def update_active_trip(self, driver_id: str, trip_id: str | None) -> None:
        """Update driver active trip."""
        driver = self.session.get(Driver, driver_id)
        if driver:
            driver.active_trip = trip_id

    def batch_create(self, drivers: list[tuple[str, DriverDNA]]) -> None:
        """Create multiple drivers at once."""
        driver_objects = []
        for driver_id, dna in drivers:
            lat, lon = dna.home_location
            driver = Driver(
                id=driver_id,
                dna_json=dna.model_dump_json(),
                current_location=f"{lat},{lon}",
                status="offline",
            )
            driver_objects.append(driver)
        self.session.add_all(driver_objects)

    def list_by_status(self, status: str) -> list[Driver]:
        """List drivers by status."""
        stmt = select(Driver).where(Driver.status == status)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

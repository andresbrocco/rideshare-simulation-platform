from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    total_drivers: int
    online_drivers: int
    total_riders: int
    waiting_riders: int
    active_trips: int
    completed_trips_today: int


class ZoneMetrics(BaseModel):
    zone_id: str
    zone_name: str
    online_drivers: int
    waiting_riders: int
    active_trips: int
    surge_multiplier: float


class TripMetrics(BaseModel):
    active_trips: int
    completed_today: int
    cancelled_today: int
    avg_fare: float
    avg_duration_minutes: float


class DriverMetrics(BaseModel):
    online: int
    offline: int
    busy: int
    en_route_pickup: int
    en_route_destination: int
    total: int

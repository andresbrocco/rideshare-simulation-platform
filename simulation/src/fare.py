from pydantic import BaseModel, Field


class FareBreakdown(BaseModel):
    """Detailed breakdown of fare components."""

    base_fee: float = Field(ge=0)
    distance_charge: float = Field(ge=0)
    time_charge: float = Field(ge=0)
    surge_multiplier: float = Field(ge=1.0)
    subtotal: float = Field(ge=0)
    total_fare: float = Field(ge=0)


class FareCalculator:
    """Calculates ride fares based on distance, duration, and surge pricing."""

    BASE_FEE = 4.00
    PER_KM_RATE = 1.50
    PER_MIN_RATE = 0.25
    MINIMUM_FARE = 8.00

    def calculate(
        self, distance_km: float, duration_min: float, surge_multiplier: float
    ) -> FareBreakdown:
        """
        Calculate fare for a trip.

        Fare is calculated once at request time based on estimated distance/duration.
        Actual trip metrics may differ but fare remains unchanged.
        """
        if distance_km < 0:
            raise ValueError("Distance must be non-negative")
        if duration_min < 0:
            raise ValueError("Duration must be non-negative")
        if surge_multiplier < 1.0:
            raise ValueError("Surge multiplier must be >= 1.0")

        base_fee = self.BASE_FEE
        distance_charge = distance_km * self.PER_KM_RATE
        time_charge = duration_min * self.PER_MIN_RATE

        subtotal = base_fee + distance_charge + time_charge
        base_total = max(subtotal, self.MINIMUM_FARE)
        total_fare = base_total * surge_multiplier

        return FareBreakdown(
            base_fee=base_fee,
            distance_charge=distance_charge,
            time_charge=time_charge,
            surge_multiplier=surge_multiplier,
            subtotal=subtotal,
            total_fare=total_fare,
        )

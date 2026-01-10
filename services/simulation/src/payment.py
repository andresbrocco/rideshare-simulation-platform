from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class Payment(BaseModel):
    """Payment processing details for completed trip."""

    payment_id: UUID
    trip_id: UUID
    rider_id: str
    driver_id: str
    payment_method_type: Literal["credit_card", "digital_wallet"]
    payment_method_masked: str
    fare_amount: float = Field(ge=0)
    platform_fee_percentage: float = 0.25
    platform_fee_amount: float = 0.0
    driver_payout_amount: float = 0.0
    timestamp: str

    @model_validator(mode="after")
    def calculate_breakdown(self) -> Self:
        self.platform_fee_amount = self.fare_amount * self.platform_fee_percentage
        self.driver_payout_amount = self.fare_amount - self.platform_fee_amount
        return self

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Rating(BaseModel):
    """Rating submitted by rider or driver after trip completion."""

    trip_id: UUID
    rater_type: Literal["rider", "driver"]
    rater_id: str
    ratee_type: Literal["rider", "driver"]
    ratee_id: str
    rating: int = Field(ge=1, le=5)
    timestamp: str

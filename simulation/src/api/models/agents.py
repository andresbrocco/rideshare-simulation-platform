from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    count: int = Field(..., ge=1, le=100)


class DriversCreateResponse(BaseModel):
    created: int
    driver_ids: list[str]


class RidersCreateResponse(BaseModel):
    created: int
    rider_ids: list[str]

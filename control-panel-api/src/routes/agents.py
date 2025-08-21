from fastapi import APIRouter, Depends, HTTPException, Request

from src.auth import verify_api_key
from src.models.agents import (
    AgentCreateRequest,
    DriversCreateResponse,
    RidersCreateResponse,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


def get_agent_factory(request: Request):
    return request.app.state.agent_factory


@router.post("/drivers", response_model=DriversCreateResponse)
def create_drivers(
    request: AgentCreateRequest, agent_factory=Depends(get_agent_factory)
):
    """Create driver agents dynamically."""
    try:
        driver_ids = agent_factory.create_drivers(request.count)
        return DriversCreateResponse(created=request.count, driver_ids=driver_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/riders", response_model=RidersCreateResponse)
def create_riders(
    request: AgentCreateRequest, agent_factory=Depends(get_agent_factory)
):
    """Create rider agents dynamically."""
    try:
        rider_ids = agent_factory.create_riders(request.count)
        return RidersCreateResponse(created=request.count, rider_ids=rider_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

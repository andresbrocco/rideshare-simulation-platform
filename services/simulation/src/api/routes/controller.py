"""Proxy routes for the performance controller service."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from api.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

CONTROLLER_URL = "http://performance-controller:8090"
TIMEOUT = 5.0


@router.get("/status")
async def get_controller_status() -> Any:
    """Proxy GET /status to the performance controller."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{CONTROLLER_URL}/status")
            return response.json()
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=503, detail="Performance controller timed out") from e
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Performance controller unreachable: {str(e)[:100]}"
        ) from e


@router.put("/mode")
async def set_controller_mode(body: dict[str, Any]) -> Any:
    """Proxy PUT /controller/mode to the performance controller."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.put(f"{CONTROLLER_URL}/controller/mode", json=body)
            return response.json()
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=503, detail="Performance controller timed out") from e
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Performance controller unreachable: {str(e)[:100]}"
        ) from e

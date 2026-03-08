"""Authentication routes — login and API key validation."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import AuthContext, verify_api_key
from api.rate_limit import limiter
from api.session_store import create_session
from api.user_store import get_user_store

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    api_key: str
    role: Literal["admin", "viewer"]
    email: str


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    """Authenticate with email and password to obtain a session API key."""
    store = get_user_store()
    record = store.verify_password(body.email, body.password)
    if record is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    redis = request.app.state.redis_client
    session = await create_session(record.email, record.role, redis)

    return LoginResponse(api_key=session.api_key, role=record.role, email=record.email)


@router.get("/validate")
async def validate_api_key_endpoint(
    _: Annotated[AuthContext, Depends(verify_api_key)],
) -> dict[str, str]:
    """Validate API key for login.

    This endpoint requires a valid API key and returns 200 if valid.
    Used by the frontend login screen to validate credentials.
    Returns 401 if the API key is invalid.
    """
    return {"status": "authenticated"}

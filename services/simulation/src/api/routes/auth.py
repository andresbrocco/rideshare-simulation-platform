"""Authentication routes — login, registration, and API key validation."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import AuthContext, require_admin, verify_api_key
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


class RegisterRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class RegisterResponse(BaseModel):
    email: str
    role: Literal["admin", "viewer"]
    status: Literal["created", "updated"]


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


@router.post("/register", response_model=RegisterResponse)
@limiter.limit("20/minute")
async def register_user(
    request: Request,
    body: RegisterRequest,
    _: Annotated[None, Depends(require_admin)],
) -> RegisterResponse:
    """Register or update a user account.  Admin API key required.

    Creates a new user with the ``viewer`` role, or updates an existing
    account's password if the email is already registered.  Callers are
    responsible for setting ``role`` — currently only ``viewer`` accounts
    can be provisioned through this endpoint, keeping provisioned visitors
    isolated from the admin account.

    This endpoint is called by the multi-service provisioning orchestrator
    (Lambda ``provision-visitor`` action) to register new visitor credentials
    in the simulation API user store.
    """
    store = get_user_store()
    existing = store.get_user(body.email)

    if existing is not None:
        # Update password by re-adding the user with the same email and role.
        # The display name (body.name) is stored in the external service UIs;
        # the user store only persists the email and bcrypt hash.
        store.add_user(body.email, body.password, existing.role)
        return RegisterResponse(email=body.email, role=existing.role, status="updated")

    record = store.add_user(body.email, body.password, "viewer")
    return RegisterResponse(email=record.email, role=record.role, status="created")


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

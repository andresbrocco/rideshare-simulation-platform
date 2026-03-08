"""User store for authentication — in-memory user registry with bcrypt password hashing."""

from typing import Literal

import bcrypt
from pydantic import BaseModel, ConfigDict


class UserRecord(BaseModel):
    """Immutable record of a stored user."""

    model_config = ConfigDict(frozen=True)

    email: str
    hashed_password: str
    role: Literal["admin", "viewer"]


class UserStore:
    """In-memory store for user records keyed by email address.

    Passwords are stored only as bcrypt hashes — plaintext is never retained.
    Writes happen exclusively at startup (provisioning), so no thread-locking
    is needed; concurrent reads in an asyncio context are safe.
    """

    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}

    def add_user(
        self,
        email: str,
        plaintext_password: str,
        role: Literal["admin", "viewer"],
    ) -> UserRecord:
        """Hash *plaintext_password*, create a UserRecord, and store it by email.

        Returns the newly created record.
        """
        hashed = bcrypt.hashpw(plaintext_password.encode(), bcrypt.gensalt()).decode()
        record = UserRecord(email=email, hashed_password=hashed, role=role)
        self._users[email] = record
        return record

    def get_user(self, email: str) -> UserRecord | None:
        """Return the UserRecord for *email*, or None if not found."""
        return self._users.get(email)

    def verify_password(self, email: str, plaintext_password: str) -> UserRecord | None:
        """Verify *plaintext_password* against the stored bcrypt hash for *email*.

        Returns the UserRecord on success, or None if the email is unknown or the
        password does not match.
        """
        record = self._users.get(email)
        if record is None:
            return None
        if bcrypt.checkpw(plaintext_password.encode(), record.hashed_password.encode()):
            return record
        return None


_user_store: UserStore | None = None


def get_user_store() -> UserStore:
    """Return the module-level singleton UserStore, creating it on first call."""
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store

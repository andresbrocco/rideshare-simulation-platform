from typing import Any

class Connection:
    async def fetchval(self, query: str, *args: Any, timeout: float | None = ...) -> Any: ...
    async def close(self, *, timeout: float | None = ...) -> None: ...

async def connect(
    dsn: str | None = ...,
    *,
    host: str | None = ...,
    port: int | None = ...,
    user: str | None = ...,
    password: str | None = ...,
    database: str | None = ...,
    timeout: float = ...,
) -> Connection: ...

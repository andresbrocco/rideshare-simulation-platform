from typing import Any, Callable, Optional, Union

class RedisCache:
    def __init__(
        self,
        host: Any = ...,
        port: int = ...,
        password: Optional[str] = ...,
        db: int = ...,
        default_timeout: int = ...,
        key_prefix: Optional[Union[str, Callable[[], str]]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any, timeout: Optional[int] = ...) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def clear(self) -> bool: ...

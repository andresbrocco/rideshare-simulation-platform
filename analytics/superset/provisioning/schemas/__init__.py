"""Table schema definitions for Bronze, Silver, and Gold layers."""

from provisioning.schemas.bronze import BRONZE_TABLES
from provisioning.schemas.gold import GOLD_TABLES
from provisioning.schemas.silver import SILVER_TABLES

__all__ = [
    "BRONZE_TABLES",
    "SILVER_TABLES",
    "GOLD_TABLES",
]

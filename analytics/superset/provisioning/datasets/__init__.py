"""Dataset definitions for Superset provisioning.

This module exports all dataset definitions organized by layer (Bronze, Silver, Gold)
and special-purpose datasets (Map).
"""

from .bronze_datasets import BRONZE_DATASETS
from .gold_datasets import GOLD_DATASETS
from .map_datasets import MAP_DATASETS
from .silver_datasets import SILVER_DATASETS

__all__ = [
    "BRONZE_DATASETS",
    "SILVER_DATASETS",
    "GOLD_DATASETS",
    "MAP_DATASETS",
]

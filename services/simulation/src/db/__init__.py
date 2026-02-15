"""Database persistence module."""

import logging
from typing import TYPE_CHECKING, Union

from .database import init_database
from .schema import Driver, Rider, SimulationMetadata, Trip
from .transaction import savepoint, transaction

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from db.checkpoint import CheckpointManager
    from db.s3_checkpoint import S3CheckpointManager
    from settings import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "init_database",
    "Driver",
    "Rider",
    "Trip",
    "SimulationMetadata",
    "transaction",
    "savepoint",
    "get_checkpoint_manager",
]


def get_checkpoint_manager(
    settings: "Settings",
    session: "Session | None" = None,
) -> Union["CheckpointManager", "S3CheckpointManager"]:
    """Get checkpoint manager based on configuration.

    Args:
        settings: Application settings
        session: SQLAlchemy session (required for SQLite backend)

    Returns:
        CheckpointManager (SQLite) or S3CheckpointManager (S3)

    Raises:
        ValueError: If storage type is s3 but boto3 is not available
        ValueError: If storage type is sqlite but session is not provided
        ValueError: If storage type is unknown
    """
    from db.checkpoint import CheckpointManager

    storage_type = settings.simulation.checkpoint_storage_type

    if storage_type == "sqlite":
        if session is None:
            raise ValueError("SQLite checkpoint backend requires session argument")
        logger.info("Using SQLite checkpoint backend")
        return CheckpointManager(session)

    if storage_type == "s3":
        try:
            import boto3
        except ImportError as exc:
            raise ValueError(
                "S3 checkpoint backend requires boto3. Install with: pip install boto3"
            ) from exc

        from db.s3_checkpoint import S3CheckpointManager

        s3_client = boto3.client("s3")

        logger.info(
            "Using S3 checkpoint backend: s3://%s/%s",
            settings.simulation.checkpoint_s3_bucket,
            settings.simulation.checkpoint_s3_prefix,
        )

        return S3CheckpointManager(
            s3_client=s3_client,
            bucket_name=settings.simulation.checkpoint_s3_bucket,
            key_prefix=settings.simulation.checkpoint_s3_prefix,
        )

    raise ValueError(
        f"Unknown checkpoint storage type: {storage_type}. " f"Expected 'sqlite' or 's3'"
    )

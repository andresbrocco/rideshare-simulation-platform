"""Database engine initialization and connection management."""

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .schema import Base, SimulationMetadata


def init_database(db_path: str) -> sessionmaker[Any]:
    """Initialize database and return session factory."""
    # Ensure parent directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    session_maker = sessionmaker(bind=engine)

    with session_maker() as session:
        schema_version = (
            session.query(SimulationMetadata).filter_by(key="schema_version").first()
        )
        if not schema_version:
            schema_version = SimulationMetadata(key="schema_version", value="1.0.0")
            session.add(schema_version)
            session.commit()

    return session_maker

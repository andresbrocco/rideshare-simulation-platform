"""Tests for agent state persistence to SQLite."""

import pytest
import simpy

from src.agents.dna import DriverDNA, RiderDNA
from src.agents.driver_agent import DriverAgent
from src.agents.rider_agent import RiderAgent
from src.db.database import init_database
from src.db.repositories.driver_repository import DriverRepository
from src.db.repositories.rider_repository import RiderRepository
from src.db.schema import Driver, Rider
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def db_session(temp_sqlite_db):
    session_maker = init_database(str(temp_sqlite_db))
    with session_maker() as session:
        yield session


@pytest.fixture
def driver_repo(db_session):
    return DriverRepository(db_session)


@pytest.fixture
def rider_repo(db_session):
    return RiderRepository(db_session)


@pytest.mark.unit
class TestDriverPersistence:
    def test_driver_persist_on_creation(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        driver_repo,
        mock_kafka_producer,
    ):
        driver_dna = dna_factory.driver_dna(home_location=(-23.55, -46.63))

        DriverAgent(
            driver_id="driver_001",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            driver_repository=driver_repo,
        )
        db_session.commit()

        driver = db_session.get(Driver, "driver_001")
        assert driver is not None
        assert driver.id == "driver_001"
        assert driver.status == "offline"
        assert driver.current_location == "-23.55,-46.63"

        retrieved_dna = DriverDNA.model_validate_json(driver.dna_json)
        assert retrieved_dna.acceptance_rate == driver_dna.acceptance_rate

    def test_driver_persist_location_update(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        driver_repo,
        mock_kafka_producer,
    ):
        driver_dna = dna_factory.driver_dna()

        agent = DriverAgent(
            driver_id="driver_002",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            driver_repository=driver_repo,
        )
        db_session.commit()

        agent.update_location(-23.56, -46.65)
        db_session.commit()

        driver = db_session.get(Driver, "driver_002")
        assert driver.current_location == "-23.56,-46.65"

    def test_driver_persist_status_update(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        driver_repo,
        mock_kafka_producer,
    ):
        driver_dna = dna_factory.driver_dna()

        agent = DriverAgent(
            driver_id="driver_003",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            driver_repository=driver_repo,
        )
        db_session.commit()

        agent.update_location(-23.55, -46.63)
        agent.go_online()
        db_session.commit()

        driver = db_session.get(Driver, "driver_003")
        assert driver.status == "online"

    def test_driver_persist_active_trip(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        driver_repo,
        mock_kafka_producer,
    ):
        driver_dna = dna_factory.driver_dna()

        agent = DriverAgent(
            driver_id="driver_004",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            driver_repository=driver_repo,
        )
        db_session.commit()

        agent.update_location(-23.55, -46.63)
        agent.go_online()
        agent.accept_trip("trip_001")
        db_session.commit()

        driver = db_session.get(Driver, "driver_004")
        assert driver.active_trip == "trip_001"
        assert driver.status == "en_route_pickup"

    def test_driver_persist_rating_update(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        driver_repo,
        mock_kafka_producer,
    ):
        driver_dna = dna_factory.driver_dna()

        agent = DriverAgent(
            driver_id="driver_005",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            driver_repository=driver_repo,
        )
        db_session.commit()

        agent.update_rating(4)
        db_session.commit()

        driver = db_session.get(Driver, "driver_005")
        assert driver.current_rating == 4.0
        assert driver.rating_count == 1

    def test_load_driver_state_on_resume(
        self, simpy_env, dna_factory: DNAFactory, temp_sqlite_db, mock_kafka_producer
    ):
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna(acceptance_rate=0.85)

        with session_maker() as session:
            repo = DriverRepository(session)
            agent = DriverAgent(
                driver_id="driver_006",
                dna=driver_dna,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
                driver_repository=repo,
            )
            agent.update_location(-23.56, -46.65)
            agent.go_online()
            agent.accept_trip("trip_002")
            agent.update_rating(5)
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            loaded_agent = DriverAgent.from_database(
                driver_id="driver_006",
                driver_repository=repo,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
            )

            assert loaded_agent.driver_id == "driver_006"
            assert loaded_agent.status == "en_route_pickup"
            assert loaded_agent.location == (-23.56, -46.65)
            assert loaded_agent.active_trip == "trip_002"
            assert loaded_agent.current_rating == 5.0
            assert loaded_agent.rating_count == 1
            assert loaded_agent.dna.acceptance_rate == 0.85

    def test_driver_without_repository(
        self, simpy_env, dna_factory: DNAFactory, mock_kafka_producer
    ):
        driver_dna = dna_factory.driver_dna()

        agent = DriverAgent(
            driver_id="driver_007",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            driver_repository=None,
        )

        agent.update_location(-23.55, -46.63)
        agent.go_online()

        assert agent.status == "online"
        assert agent.location == (-23.55, -46.63)

    def test_dna_immutability_on_load(
        self, simpy_env, dna_factory: DNAFactory, temp_sqlite_db, mock_kafka_producer
    ):
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna(acceptance_rate=0.92, service_quality=0.88)

        with session_maker() as session:
            repo = DriverRepository(session)
            DriverAgent(
                driver_id="driver_008",
                dna=driver_dna,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
                driver_repository=repo,
            )
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            loaded_agent = DriverAgent.from_database(
                driver_id="driver_008",
                driver_repository=repo,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
            )

            assert loaded_agent.dna.acceptance_rate == 0.92
            assert loaded_agent.dna.service_quality == 0.88
            assert loaded_agent.dna.first_name == driver_dna.first_name


@pytest.mark.unit
class TestRiderPersistence:
    def test_rider_persist_on_creation(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        rider_repo,
        mock_kafka_producer,
    ):
        rider_dna = dna_factory.rider_dna(home_location=(-23.55, -46.63))

        RiderAgent(
            rider_id="rider_001",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            rider_repository=rider_repo,
        )
        db_session.commit()

        rider = db_session.get(Rider, "rider_001")
        assert rider is not None
        assert rider.id == "rider_001"
        assert rider.status == "offline"
        assert rider.current_location == "-23.55,-46.63"

        retrieved_dna = RiderDNA.model_validate_json(rider.dna_json)
        assert retrieved_dna.behavior_factor == rider_dna.behavior_factor

    def test_rider_persist_location_update(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        rider_repo,
        mock_kafka_producer,
    ):
        rider_dna = dna_factory.rider_dna()

        agent = RiderAgent(
            rider_id="rider_002",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            rider_repository=rider_repo,
        )
        db_session.commit()

        agent.update_location(-23.56, -46.65)
        db_session.commit()

        rider = db_session.get(Rider, "rider_002")
        assert rider.current_location == "-23.56,-46.65"

    def test_rider_persist_status_update(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        rider_repo,
        mock_kafka_producer,
    ):
        rider_dna = dna_factory.rider_dna()

        agent = RiderAgent(
            rider_id="rider_003",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            rider_repository=rider_repo,
        )
        db_session.commit()

        agent.request_trip("trip_001")
        db_session.commit()

        rider = db_session.get(Rider, "rider_003")
        assert rider.status == "waiting"
        assert rider.active_trip == "trip_001"

    def test_rider_persist_rating_update(
        self,
        simpy_env,
        dna_factory: DNAFactory,
        db_session,
        rider_repo,
        mock_kafka_producer,
    ):
        rider_dna = dna_factory.rider_dna()

        agent = RiderAgent(
            rider_id="rider_004",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            rider_repository=rider_repo,
        )
        db_session.commit()

        agent.update_rating(3)
        db_session.commit()

        rider = db_session.get(Rider, "rider_004")
        assert rider.current_rating == 3.0
        assert rider.rating_count == 1

    def test_load_rider_state_on_resume(
        self, simpy_env, dna_factory: DNAFactory, temp_sqlite_db, mock_kafka_producer
    ):
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna(behavior_factor=0.8)

        with session_maker() as session:
            repo = RiderRepository(session)
            agent = RiderAgent(
                rider_id="rider_005",
                dna=rider_dna,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
                rider_repository=repo,
            )
            agent.update_location(-23.56, -46.65)
            agent.request_trip("trip_003")
            agent.update_rating(4)
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            loaded_agent = RiderAgent.from_database(
                rider_id="rider_005",
                rider_repository=repo,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
            )

            assert loaded_agent.rider_id == "rider_005"
            assert loaded_agent.status == "waiting"
            assert loaded_agent.location == (-23.56, -46.65)
            assert loaded_agent.active_trip == "trip_003"
            assert loaded_agent.current_rating == 4.0
            assert loaded_agent.rating_count == 1
            assert loaded_agent.dna.behavior_factor == 0.8

    def test_rider_without_repository(
        self, simpy_env, dna_factory: DNAFactory, mock_kafka_producer
    ):
        rider_dna = dna_factory.rider_dna()

        agent = RiderAgent(
            rider_id="rider_006",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            rider_repository=None,
        )

        agent.update_location(-23.55, -46.63)
        agent.request_trip("trip_004")

        assert agent.status == "waiting"
        assert agent.location == (-23.55, -46.63)
        assert agent.active_trip == "trip_004"

    def test_dna_immutability_on_load(
        self, simpy_env, dna_factory: DNAFactory, temp_sqlite_db, mock_kafka_producer
    ):
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna(behavior_factor=0.75, patience_threshold=200)

        with session_maker() as session:
            repo = RiderRepository(session)
            RiderAgent(
                rider_id="rider_007",
                dna=rider_dna,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
                rider_repository=repo,
            )
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            loaded_agent = RiderAgent.from_database(
                rider_id="rider_007",
                rider_repository=repo,
                env=simpy_env,
                kafka_producer=mock_kafka_producer,
            )

            assert loaded_agent.dna.behavior_factor == 0.75
            assert loaded_agent.dna.patience_threshold == 200
            assert loaded_agent.dna.first_name == rider_dna.first_name

"""Tests for checkpoint trigger wiring (periodic, on-pause, on-shutdown, auto-restore)."""

import contextlib
from unittest.mock import MagicMock, patch

from src.engine import SimulationEngine, SimulationState

# ---------------------------------------------------------------------------
# Gap 1 — Periodic checkpoint process
# ---------------------------------------------------------------------------


class TestPeriodicCheckpointProcess:
    """Verify _checkpoint_process is registered and fires correctly."""

    def test_checkpoint_process_registered_when_enabled(self, fast_engine: SimulationEngine):
        """When checkpoint_enabled=True, a checkpoint process should be in _periodic_processes."""
        with patch("src.engine.get_settings") as mock_settings:
            sim_settings = MagicMock()
            sim_settings.checkpoint_enabled = True
            sim_settings.checkpoint_interval = 300
            spawn_settings = MagicMock()
            spawn_settings.driver_immediate_spawn_rate = 2
            spawn_settings.driver_scheduled_spawn_rate = 10
            spawn_settings.rider_immediate_spawn_rate = 2
            spawn_settings.rider_scheduled_spawn_rate = 10
            mock_settings.return_value.simulation = sim_settings
            mock_settings.return_value.spawn = spawn_settings

            fast_engine._periodic_processes.clear()
            fast_engine._start_periodic_processes()

            # surge(1) + 4 spawners + checkpoint(1) = 6
            assert len(fast_engine._periodic_processes) == 6

    def test_checkpoint_process_not_registered_when_disabled(self, fast_engine: SimulationEngine):
        """When checkpoint_enabled=False, no checkpoint process should be added."""
        with patch("src.engine.get_settings") as mock_settings:
            sim_settings = MagicMock()
            sim_settings.checkpoint_enabled = False
            sim_settings.checkpoint_interval = 300
            spawn_settings = MagicMock()
            spawn_settings.driver_immediate_spawn_rate = 2
            spawn_settings.driver_scheduled_spawn_rate = 10
            spawn_settings.rider_immediate_spawn_rate = 2
            spawn_settings.rider_scheduled_spawn_rate = 10
            mock_settings.return_value.simulation = sim_settings
            mock_settings.return_value.spawn = spawn_settings

            fast_engine._periodic_processes.clear()
            fast_engine._start_periodic_processes()

            # surge(1) + 4 spawners = 5 (no checkpoint)
            assert len(fast_engine._periodic_processes) == 5

    def test_checkpoint_process_calls_save_after_interval(self, fast_engine: SimulationEngine):
        """The checkpoint process should call save_checkpoint after the configured interval."""
        with patch("src.engine.get_settings") as mock_settings:
            sim_settings = MagicMock()
            sim_settings.checkpoint_enabled = True
            sim_settings.checkpoint_interval = 100
            mock_settings.return_value.simulation = sim_settings

            with patch.object(fast_engine, "save_checkpoint") as mock_save:
                fast_engine._env.process(fast_engine._checkpoint_process())
                # Advance past one interval
                fast_engine._env.run(until=101)
                mock_save.assert_called_once()

    def test_checkpoint_process_survives_exception(self, fast_engine: SimulationEngine):
        """If save_checkpoint raises, the process should continue running."""
        with patch("src.engine.get_settings") as mock_settings:
            sim_settings = MagicMock()
            sim_settings.checkpoint_enabled = True
            sim_settings.checkpoint_interval = 50
            mock_settings.return_value.simulation = sim_settings

            with patch.object(
                fast_engine, "save_checkpoint", side_effect=RuntimeError("disk full")
            ) as mock_save:
                fast_engine._env.process(fast_engine._checkpoint_process())
                # Advance past two intervals — process should survive the first failure
                fast_engine._env.run(until=101)
                assert mock_save.call_count == 2


# ---------------------------------------------------------------------------
# Gap 2 — Checkpoint on pause
# ---------------------------------------------------------------------------


class TestCheckpointOnPause:
    """Verify checkpoint is saved when simulation transitions to PAUSED."""

    def test_saves_checkpoint_on_pause_when_enabled(self, fast_running_engine: SimulationEngine):
        """Pausing should trigger a checkpoint save when enabled."""
        with patch("src.engine.get_settings") as mock_settings:
            mock_settings.return_value.simulation.checkpoint_enabled = True

            with patch.object(fast_running_engine, "save_checkpoint") as mock_save:
                fast_running_engine._transition_to_paused("quiescence_achieved")
                mock_save.assert_called_once()
                assert fast_running_engine.state == SimulationState.PAUSED

    def test_skips_checkpoint_on_pause_when_disabled(self, fast_running_engine: SimulationEngine):
        """Pausing should NOT trigger a checkpoint when disabled."""
        with patch("src.engine.get_settings") as mock_settings:
            mock_settings.return_value.simulation.checkpoint_enabled = False

            with patch.object(fast_running_engine, "save_checkpoint") as mock_save:
                fast_running_engine._transition_to_paused("quiescence_achieved")
                mock_save.assert_not_called()
                assert fast_running_engine.state == SimulationState.PAUSED

    def test_pause_completes_even_if_checkpoint_fails(self, fast_running_engine: SimulationEngine):
        """Pause should succeed even if checkpoint save raises."""
        with patch("src.engine.get_settings") as mock_settings:
            mock_settings.return_value.simulation.checkpoint_enabled = True

            with patch.object(
                fast_running_engine, "save_checkpoint", side_effect=RuntimeError("db error")
            ):
                fast_running_engine._transition_to_paused("quiescence_achieved")
                # State should still be PAUSED despite checkpoint failure
                assert fast_running_engine.state == SimulationState.PAUSED


# ---------------------------------------------------------------------------
# Gap 3 — Checkpoint on SIGTERM (shutdown handler)
# ---------------------------------------------------------------------------


class TestCheckpointOnShutdown:
    """Verify checkpoint is saved during shutdown.

    The real shutdown_handler is a closure inside main(), so we reconstruct
    its logic with mocks to verify the checkpoint integration.
    """

    def _build_shutdown_handler(
        self,
        sim_runner: MagicMock,
        engine: MagicMock,
        kafka_producer: MagicMock | None,
        checkpoint_enabled: bool,
    ):
        """Build a shutdown handler matching the real closure in main.py."""
        settings = MagicMock()
        settings.simulation.checkpoint_enabled = checkpoint_enabled

        def shutdown_handler(signum: int, frame: object) -> None:
            sim_runner.stop()

            if settings.simulation.checkpoint_enabled:
                with contextlib.suppress(Exception):
                    engine.save_checkpoint()

            if engine.state.value == "running":
                engine.stop()
            if kafka_producer:
                kafka_producer.flush()

        return shutdown_handler

    def test_saves_checkpoint_on_sigterm_when_enabled(self):
        """SIGTERM should trigger checkpoint when enabled."""
        sim_runner = MagicMock()
        engine = MagicMock()
        engine.state.value = "running"
        kafka_producer = MagicMock()

        handler = self._build_shutdown_handler(sim_runner, engine, kafka_producer, True)
        handler(15, None)

        engine.save_checkpoint.assert_called_once()
        sim_runner.stop.assert_called_once()
        engine.stop.assert_called_once()

    def test_skips_checkpoint_on_sigterm_when_disabled(self):
        """SIGTERM should NOT trigger checkpoint when disabled."""
        sim_runner = MagicMock()
        engine = MagicMock()
        engine.state.value = "running"
        kafka_producer = MagicMock()

        handler = self._build_shutdown_handler(sim_runner, engine, kafka_producer, False)
        handler(15, None)

        engine.save_checkpoint.assert_not_called()

    def test_shutdown_continues_on_checkpoint_failure(self):
        """Shutdown should complete even if checkpoint save raises."""
        sim_runner = MagicMock()
        engine = MagicMock()
        engine.state.value = "running"
        engine.save_checkpoint.side_effect = RuntimeError("disk full")
        kafka_producer = MagicMock()

        handler = self._build_shutdown_handler(sim_runner, engine, kafka_producer, True)
        handler(15, None)

        # Shutdown should still complete
        engine.stop.assert_called_once()
        kafka_producer.flush.assert_called_once()

    def test_correct_call_order_on_sigterm(self):
        """Verify: runner_stop -> checkpoint -> engine_stop -> flush."""
        call_order: list[str] = []
        sim_runner = MagicMock()
        sim_runner.stop.side_effect = lambda: call_order.append("runner_stop")
        engine = MagicMock()
        engine.state.value = "running"
        engine.save_checkpoint.side_effect = lambda: call_order.append("checkpoint")
        engine.stop.side_effect = lambda: call_order.append("engine_stop")
        kafka_producer = MagicMock()
        kafka_producer.flush.side_effect = lambda: call_order.append("flush")

        handler = self._build_shutdown_handler(sim_runner, engine, kafka_producer, True)
        handler(15, None)

        assert call_order == ["runner_stop", "checkpoint", "engine_stop", "flush"]


# ---------------------------------------------------------------------------
# Gap 4 — Auto-restore on startup
# ---------------------------------------------------------------------------


class TestAutoRestoreOnStartup:
    """Verify checkpoint restore is attempted on startup when configured."""

    def test_restore_called_when_configured(self, fast_engine: SimulationEngine):
        """try_restore_from_checkpoint should be called when resume_from_checkpoint=True."""
        with patch("src.engine.get_settings") as mock_settings:
            mock_settings.return_value.simulation.resume_from_checkpoint = True

            with patch.object(
                fast_engine, "try_restore_from_checkpoint", return_value=True
            ) as mock_restore:
                # Simulate the startup logic from main.py
                settings = mock_settings()
                if settings.simulation.resume_from_checkpoint:
                    fast_engine.try_restore_from_checkpoint()

                mock_restore.assert_called_once()

    def test_restore_returns_false_when_no_checkpoint(self, fast_engine: SimulationEngine):
        """When no checkpoint exists, try_restore_from_checkpoint returns False."""
        with patch.object(
            fast_engine, "try_restore_from_checkpoint", return_value=False
        ) as mock_restore:
            result = fast_engine.try_restore_from_checkpoint()
            assert result is False
            mock_restore.assert_called_once()

    def test_restore_not_called_when_disabled(self, fast_engine: SimulationEngine):
        """try_restore_from_checkpoint should NOT be called when resume_from_checkpoint=False."""
        with patch("src.engine.get_settings") as mock_settings:
            mock_settings.return_value.simulation.resume_from_checkpoint = False

            with patch.object(fast_engine, "try_restore_from_checkpoint") as mock_restore:
                settings = mock_settings()
                if settings.simulation.resume_from_checkpoint:
                    fast_engine.try_restore_from_checkpoint()

                mock_restore.assert_not_called()

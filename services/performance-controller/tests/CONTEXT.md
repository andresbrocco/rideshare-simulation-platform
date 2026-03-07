# CONTEXT.md — Performance Controller Tests

## Purpose

Unit tests for the performance controller's core algorithmic logic: the `_snap_to_floor_power_of_two` helper, mode switching (`set_mode`), and the asymmetric PID-based `decide_speed` controller. All tests run outside Docker by mocking external dependencies.

## Responsibility Boundaries

- **Owns**: Behavioral verification of `PerformanceController` and `_snap_to_floor_power_of_two` in isolation
- **Delegates to**: `src.controller` and `src.settings` for the implementation under test
- **Does not handle**: Integration testing against a live simulation API or Prometheus endpoint

## Non-Obvious Details

- `conftest.py` stubs the entire `opentelemetry` module tree into `sys.modules` before any `src.*` import. This must happen at collection time, not inside a fixture, because Python caches module imports on first load. If `opentelemetry` is imported by `src.metrics_exporter` before the stub is in place, the real package (absent outside Docker) causes an `ImportError`.
- The `decide_speed` tests use two separate helper factories (`_make_controller` and `_make_controller_with_speed`) because `decide_speed` behavior depends on `_current_speed` state that must be set after construction.
- The asymmetry tests (`test_asymmetry_decrease_larger_than_increase`) encode a deliberate design invariant: the controller cuts speed much more aggressively than it raises it (`k_down` >> `k_up`). Tests verify the ratio is at least 2:1, serving as a regression guard for future tuning changes.
- PID integral and derivative tests reset `_current_speed` mid-loop to isolate the factor contribution from cumulative speed drift; without this reset, compounding speed changes would obscure which term is under test.
- `test_derivative_skipped_on_first_cycle` confirms that the D-term is zero on the very first `decide_speed` call (no `previous_error` yet), enforcing the initialization contract.

"""Resource model fitting for scaling predictions."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from scipy import optimize


class FitType(Enum):
    """Types of curve fits for resource modeling."""

    LINEAR = "linear"
    POWER = "power"
    LOGARITHMIC = "logarithmic"
    EXPONENTIAL = "exponential"


@dataclass
class FitResult:
    """Result of a curve fit."""

    fit_type: FitType
    formula: str
    r_squared: float
    coefficients: dict[str, float]
    predictions: list[float]


class ResourceModelFitter:
    """Fits resource usage data to various models.

    Fits types: LINEAR, POWER, LOGARITHMIC, EXPONENTIAL
    """

    def __init__(self) -> None:
        pass

    def _linear_func(self, x: np.ndarray, a: float, b: float) -> np.ndarray:
        """Linear: y = a*x + b"""
        return a * x + b

    def _power_func(self, x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        """Power: y = a * x^b + c"""
        return a * np.power(x + 0.1, b) + c  # Add small offset to avoid x=0 issues

    def _log_func(self, x: np.ndarray, a: float, b: float) -> np.ndarray:
        """Logarithmic: y = a * ln(x) + b"""
        result: np.ndarray = a * np.log(x + 1) + b  # Add 1 to avoid ln(0)
        return result

    def _exp_func(self, x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        """Exponential: y = a * e^(b*x) + c"""
        return a * np.exp(b * x) + c

    def _calculate_r_squared(self, y_actual: np.ndarray, y_predicted: np.ndarray) -> float:
        """Calculate R-squared (coefficient of determination)."""
        ss_res = np.sum((y_actual - y_predicted) ** 2)
        ss_tot = np.sum((y_actual - np.mean(y_actual)) ** 2)
        if ss_tot == 0:
            return 0.0
        return float(1 - (ss_res / ss_tot))

    def _fit_linear(self, x: np.ndarray, y: np.ndarray) -> tuple[FitResult, np.ndarray] | None:
        """Fit linear model."""
        try:
            popt, _ = optimize.curve_fit(self._linear_func, x, y)
            a, b = popt
            predictions = self._linear_func(x, a, b)
            r_squared = self._calculate_r_squared(y, predictions)

            # Format formula
            formula = f"memory_mb = {a:.2f} * agents + {b:.1f}"

            return (
                FitResult(
                    fit_type=FitType.LINEAR,
                    formula=formula,
                    r_squared=r_squared,
                    coefficients={"slope": a, "intercept": b},
                    predictions=predictions.tolist(),
                ),
                predictions,
            )
        except Exception:
            return None

    def _fit_power(self, x: np.ndarray, y: np.ndarray) -> tuple[FitResult, np.ndarray] | None:
        """Fit power model."""
        try:
            # Initial guess
            popt, _ = optimize.curve_fit(
                self._power_func,
                x,
                y,
                p0=[1.0, 1.0, y.min()],
                maxfev=5000,
            )
            a, b, c = popt
            predictions = self._power_func(x, a, b, c)
            r_squared = self._calculate_r_squared(y, predictions)

            formula = f"memory_mb = {a:.2f} * agents^{b:.2f} + {c:.1f}"

            return (
                FitResult(
                    fit_type=FitType.POWER,
                    formula=formula,
                    r_squared=r_squared,
                    coefficients={"coefficient": a, "exponent": b, "offset": c},
                    predictions=predictions.tolist(),
                ),
                predictions,
            )
        except Exception:
            return None

    def _fit_logarithmic(self, x: np.ndarray, y: np.ndarray) -> tuple[FitResult, np.ndarray] | None:
        """Fit logarithmic model."""
        try:
            popt, _ = optimize.curve_fit(self._log_func, x, y)
            a, b = popt
            predictions = self._log_func(x, a, b)
            r_squared = self._calculate_r_squared(y, predictions)

            formula = f"memory_mb = {a:.2f} * ln(agents + 1) + {b:.1f}"

            return (
                FitResult(
                    fit_type=FitType.LOGARITHMIC,
                    formula=formula,
                    r_squared=r_squared,
                    coefficients={"coefficient": a, "offset": b},
                    predictions=predictions.tolist(),
                ),
                predictions,
            )
        except Exception:
            return None

    def _fit_exponential(self, x: np.ndarray, y: np.ndarray) -> tuple[FitResult, np.ndarray] | None:
        """Fit exponential model."""
        try:
            # Initial guess - small growth rate
            popt, _ = optimize.curve_fit(
                self._exp_func,
                x,
                y,
                p0=[1.0, 0.01, y.min()],
                maxfev=5000,
            )
            a, b, c = popt
            predictions = self._exp_func(x, a, b, c)
            r_squared = self._calculate_r_squared(y, predictions)

            formula = f"memory_mb = {a:.2f} * e^({b:.4f} * agents) + {c:.1f}"

            return (
                FitResult(
                    fit_type=FitType.EXPONENTIAL,
                    formula=formula,
                    r_squared=r_squared,
                    coefficients={"coefficient": a, "growth_rate": b, "offset": c},
                    predictions=predictions.tolist(),
                ),
                predictions,
            )
        except Exception:
            return None

    def fit_all(
        self, x: list[int] | list[float] | np.ndarray, y: list[int] | list[float] | np.ndarray
    ) -> list[FitResult]:
        """Fit all model types and return sorted by R-squared.

        Args:
            x: Independent variable (e.g., agent count).
            y: Dependent variable (e.g., memory usage).

        Returns:
            List of FitResult sorted by R-squared (best first).
        """
        x_arr = np.array(x, dtype=float)
        y_arr = np.array(y, dtype=float)

        if len(x_arr) < 2:
            return []

        results: list[FitResult] = []

        # Try each fit type
        for fit_func in [
            self._fit_linear,
            self._fit_power,
            self._fit_logarithmic,
            self._fit_exponential,
        ]:
            result = fit_func(x_arr, y_arr)
            if result is not None:
                results.append(result[0])

        # Sort by R-squared (best first)
        results.sort(key=lambda r: r.r_squared, reverse=True)

        return results

    def get_best_fit(
        self, x: list[int] | list[float] | np.ndarray, y: list[int] | list[float] | np.ndarray
    ) -> FitResult | None:
        """Get the best fitting model.

        Args:
            x: Independent variable.
            y: Dependent variable.

        Returns:
            Best FitResult, or None if no fit succeeded.
        """
        results = self.fit_all(x, y)
        return results[0] if results else None


def fit_load_scaling_all_containers(
    scenario_results: list[dict[str, Any]],
    container_names: list[str] | None = None,
    metrics: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Fit resource models for all containers and metrics.

    Args:
        scenario_results: List of scenario result dicts from load scaling tests.
        container_names: Containers to analyze (None = all containers found).
        metrics: Metrics to fit ("memory", "cpu"). Default: ["memory", "cpu"].

    Returns:
        Dict: {container: {memory: {best_fit, all_fits, data_points}, cpu: {...}}}
    """
    from .statistics import calculate_stats

    if metrics is None:
        metrics = ["memory", "cpu"]

    # Find all containers from samples if not specified
    if container_names is None:
        containers_found: set[str] = set()
        for result in scenario_results:
            if not result["scenario_name"].startswith("load_scaling_"):
                continue
            samples = result.get("samples", [])
            for sample in samples:
                containers_found.update(sample.get("containers", {}).keys())
        container_names = sorted(containers_found)

    results: dict[str, dict[str, Any]] = {}

    for container_name in container_names:
        container_results: dict[str, Any] = {}

        for metric in metrics:
            # Extract data points for this container/metric
            data_points: list[tuple[int, float]] = []

            for result in scenario_results:
                if not result["scenario_name"].startswith("load_scaling_"):
                    continue

                agent_count = result["scenario_params"].get("total_agents", 0)
                samples = result.get("samples", [])

                stats = calculate_stats(samples, container_name)
                if stats is not None:
                    if metric == "memory":
                        data_points.append((agent_count, stats.memory_mean))
                    elif metric == "cpu":
                        data_points.append((agent_count, stats.cpu_mean))

            if not data_points:
                container_results[metric] = {"error": "No data points found"}
                continue

            # Sort by agent count
            data_points.sort(key=lambda p: p[0])

            x = [p[0] for p in data_points]
            y = [p[1] for p in data_points]

            # Fit models
            fitter = ResourceModelFitter()
            all_fits = fitter.fit_all(x, y)

            if not all_fits:
                container_results[metric] = {"error": "No fits succeeded"}
                continue

            # Update formula strings to reflect metric type
            metric_unit = "memory_mb" if metric == "memory" else "cpu_percent"
            for fit in all_fits:
                fit.formula = fit.formula.replace("memory_mb", metric_unit)

            best_fit = all_fits[0]

            container_results[metric] = {
                "data_points": data_points,
                "best_fit": {
                    "fit_type": best_fit.fit_type.value,
                    "formula": best_fit.formula,
                    "r_squared": best_fit.r_squared,
                    "coefficients": best_fit.coefficients,
                },
                "all_fits": [
                    {
                        "fit_type": f.fit_type.value,
                        "formula": f.formula,
                        "r_squared": f.r_squared,
                    }
                    for f in all_fits
                ],
            }

        results[container_name] = container_results

    return results

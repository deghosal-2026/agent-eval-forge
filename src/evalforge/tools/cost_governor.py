"""Cost governor — enforces cost ceilings during evaluation runs (X22).

Monitors accumulating cost across scenarios and aborts runs that exceed
configured budgets. Integrates with the Runner to stop early.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CostConfig:
    """Budget configuration for the cost governor.

    Attributes:
        max_total_cost_usd: Hard ceiling for total spend across all scenarios.
        max_per_scenario_cost_usd: Ceiling for any single scenario.
        max_total_tokens: Hard ceiling for total token usage.
        abort_on_threshold: Whether to abort the run when over budget.
        warn_at_percent: Fraction of max_total_cost_usd at which to emit a warning.
    """
    max_total_cost_usd: float = 1.00
    max_per_scenario_cost_usd: float = 0.10
    max_total_tokens: int = 100_000
    abort_on_threshold: bool = True
    warn_at_percent: float = 0.8


@dataclass
class CostStatus:
    """Current cost-tracking state.

    Attributes:
        total_cost_usd: Accumulated cost in USD.
        total_tokens: Accumulated token count.
        scenarios_run: Number of scenarios completed so far.
        scenarios_aborted: Number of scenarios aborted due to budget.
        over_budget: Flag indicating the budget has been exceeded.
        remaining_budget_usd: Budget left before hitting the ceiling.
    """
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    scenarios_run: int = 0
    scenarios_aborted: int = 0
    over_budget: bool = False
    remaining_budget_usd: float = 0.0


class CostGovernor:
    """Monitors and enforces cost limits during evaluation runs."""

    def __init__(self, config: CostConfig | None = None) -> None:
        """Initialise governor with a cost configuration.

        Args:
            config: :class:`CostConfig`; uses defaults if ``None``.
        """
        self._config = config or CostConfig()
        self._status = CostStatus(remaining_budget_usd=self._config.max_total_cost_usd)

    @property
    def status(self) -> CostStatus:
        """Return the current :class:`CostStatus` snapshot."""
        return self._status

    def can_run_scenario(self, estimated_cost: float = 0.0) -> bool:
        """Check whether a scenario with the given estimated cost can proceed.

        Rejects if already over budget, if the estimate exceeds the per-scenario
        limit, or if remaining budget is insufficient.

        Args:
            estimated_cost: Anticipated cost for the next scenario.

        Returns:
            ``True`` if the scenario is allowed to run.
        """
        if self._status.over_budget:
            return False
        remaining = self._config.max_total_cost_usd - self._status.total_cost_usd
        if estimated_cost > self._config.max_per_scenario_cost_usd:
            return False
        return remaining >= estimated_cost

    def record_scenario(self, cost_usd: float, tokens: int) -> CostStatus:
        """Record completed scenario costs and update budget state.

        Args:
            cost_usd: Actual cost incurred.
            tokens: Actual tokens consumed.

        Returns:
            Updated :class:`CostStatus`.
        """
        self._status.total_cost_usd += cost_usd
        self._status.total_tokens += tokens
        self._status.scenarios_run += 1
        self._status.remaining_budget_usd = (
            self._config.max_total_cost_usd - self._status.total_cost_usd
        )
        if self._status.total_cost_usd >= self._config.max_total_cost_usd:
            self._status.over_budget = True
        if self._status.total_tokens >= self._config.max_total_tokens:
            self._status.over_budget = True
        return self._status

    def record_aborted(self) -> None:
        """Increment the aborted-scenario counter."""
        self._status.scenarios_aborted += 1

    def should_warn(self) -> bool:
        """Check whether the spend has reached the warning threshold.

        Returns:
            ``True`` if ``total_cost_usd / max_total_cost_usd >= warn_at_percent``.
        """
        ratio = self._status.total_cost_usd / self._config.max_total_cost_usd
        return ratio >= self._config.warn_at_percent

    def remaining_scenarios_estimate(self, avg_cost_per_scenario: float) -> int:
        """Estimate how many more scenarios can be run given average cost.

        Args:
            avg_cost_per_scenario: Historic average cost per scenario.

        Returns:
            Integer estimate (capped at 999 if avg_cost <= 0).
        """
        if avg_cost_per_scenario <= 0:
            return 999
        remaining = self._config.max_total_cost_usd - self._status.total_cost_usd
        return max(0, int(remaining / avg_cost_per_scenario))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the current status and configuration to a dict.

        Returns:
            Dict with all relevant cost fields.
        """
        return {
            "total_cost_usd": round(self._status.total_cost_usd, 6),
            "total_tokens": self._status.total_tokens,
            "scenarios_run": self._status.scenarios_run,
            "scenarios_aborted": self._status.scenarios_aborted,
            "over_budget": self._status.over_budget,
            "remaining_budget_usd": round(self._status.remaining_budget_usd, 6),
            "max_total_cost_usd": self._config.max_total_cost_usd,
            "max_total_tokens": self._config.max_total_tokens,
        }

    def reset(self) -> None:
        """Reset the governor to its initial state (zero cost)."""
        self._status = CostStatus(remaining_budget_usd=self._config.max_total_cost_usd)

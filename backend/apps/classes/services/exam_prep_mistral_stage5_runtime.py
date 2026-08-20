"""Small document-level cost/deadline controls for Stage 5."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
from typing import Any


_TASK_DEADLINE: ContextVar[float | None] = ContextVar(
    "exam_prep_stage5_task_deadline",
    default=None,
)
_MILLION = Decimal("1000000")
_MODEL_RATES: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("4.50")),
    "gemini-3.6-flash": (Decimal("1.50"), Decimal("7.50")),
}


class Stage5CostBudgetExceeded(RuntimeError):
    """No new provider call may start inside the remaining dollar budget."""


@contextmanager
def stage5_task_deadline(deadline_at: float | None):
    """Expose the Celery deadline without changing the public pipeline API."""

    token = _TASK_DEADLINE.set(deadline_at)
    try:
        yield
    finally:
        _TASK_DEADLINE.reset(token)


def current_stage5_task_deadline() -> float | None:
    return _TASK_DEADLINE.get()


def _money(value: Any) -> Decimal:
    try:
        return max(Decimal("0"), Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
) -> Decimal | None:
    rates = _MODEL_RATES.get(model)
    if rates is None:
        return None
    return (
        Decimal(max(0, int(input_tokens))) * rates[0]
        + Decimal(max(0, int(output_tokens))) * rates[1]
    ) / _MILLION


def _reported_usage(value: Any) -> tuple[int, int]:
    """Return priceable usage only when both token sides are provider-reported."""

    try:
        input_tokens = max(0, int(getattr(value, "input_tokens", 0) or 0))
        output_tokens = max(0, int(getattr(value, "output_tokens", 0) or 0))
    except (TypeError, ValueError):
        return 0, 0
    return input_tokens, output_tokens


@dataclass(frozen=True, slots=True)
class _Reservation:
    model: str
    amount: Decimal


class Stage5BudgetLedger:
    """Rolling reservation ledger; all mutation happens on the caller thread."""

    def __init__(self, *, max_cost_usd: Any, max_output_tokens: int) -> None:
        self.cap = _money(max_cost_usd)
        self.max_output_tokens = max(0, int(max_output_tokens))
        self.reserved_input_tokens = _int_env(
            "EXAM_PREP_STAGE5_RESERVED_INPUT_TOKENS",
            8192,
            minimum=1000,
            maximum=32768,
        )
        self.charged = Decimal("0")
        self.reserved = Decimal("0")
        self.success_cost = Decimal("0")
        self.failure_cost = Decimal("0")
        self.maximum_exposure = Decimal("0")
        self.failed_calls = 0
        self.success_calls_charged_at_reservation = 0
        self.blocked_calls = 0
        self.cost_estimate_complete = True
        self.cost_cap_exceeded = False

    def reservation_for(self, model: str) -> Decimal | None:
        return _cost_usd(
            model,
            input_tokens=self.reserved_input_tokens,
            output_tokens=self.max_output_tokens,
        )

    def reserve(self, model: str) -> _Reservation | None:
        amount = self.reservation_for(model)
        if amount is None:
            self.cost_estimate_complete = False
            return None
        if self.charged + self.reserved + amount > self.cap:
            return None
        self.reserved += amount
        self.maximum_exposure = max(
            self.maximum_exposure,
            self.charged + self.reserved,
        )
        return _Reservation(model=model, amount=amount)

    def release(self, reservation: _Reservation) -> None:
        self.reserved = max(Decimal("0"), self.reserved - reservation.amount)

    def settle(self, reservation: _Reservation, value: Any) -> None:
        self.release(reservation)
        if isinstance(value, Exception):
            cost = reservation.amount
            self.failed_calls += 1
            self.failure_cost += cost
        else:
            input_tokens, output_tokens = _reported_usage(value)
            resolved_model = str(
                getattr(value, "model", reservation.model) or reservation.model
            )
            cost = (
                _cost_usd(
                    resolved_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                if input_tokens > 0 and output_tokens > 0
                else None
            )
            if cost is None:
                # A successful response without complete provider usage must not
                # free its reservation and make the document budget look cheaper
                # than it can be proven to be. Charge the conservative reservation
                # and mark the estimate incomplete instead.
                self.cost_estimate_complete = False
                cost = reservation.amount
                self.success_calls_charged_at_reservation += 1
            self.success_cost += cost
        self.charged += cost
        if self.charged + self.reserved > self.cap:
            self.cost_cap_exceeded = True
            self.cost_estimate_complete = False

    def record_blocked(self, count: int) -> None:
        self.blocked_calls += max(0, int(count))
        self.cost_cap_exceeded = self.cost_cap_exceeded or count > 0

    def safe_dict(self) -> dict[str, Any]:
        return {
            "costCapEnabled": True,
            "costCapUsd": format(self.cap, "f"),
            "successfulCallEstimatedCostUsd": format(self.success_cost, "f"),
            "failedCallReservedCostUsd": format(self.failure_cost, "f"),
            "chargedCostUsd": format(self.charged, "f"),
            "reservedInFlightCostUsd": format(self.reserved, "f"),
            "maximumReservedExposureUsd": format(self.maximum_exposure, "f"),
            "reservedInputTokensPerCall": self.reserved_input_tokens,
            "costEstimateComplete": self.cost_estimate_complete,
            "costCapExceeded": self.cost_cap_exceeded,
            "budgetBlockedCalls": self.blocked_calls,
            "failedCallsChargedAtReservation": self.failed_calls,
            "successfulCallsChargedAtReservation": self.success_calls_charged_at_reservation,
        }


def successful_call_cost_usd(stage5_audit: Mapping[str, Any]) -> tuple[Decimal, bool]:
    """Price successful calls from their provider-reported token usage."""

    total = Decimal("0")
    complete = True
    for row in stage5_audit.get("regions") or []:
        if not isinstance(row, Mapping):
            continue
        for key in ("primary", "main"):
            call = row.get(key)
            if not isinstance(call, Mapping):
                continue
            input_tokens = int(call.get("inputTokens") or 0)
            output_tokens = int(call.get("outputTokens") or 0)
            if input_tokens <= 0 or output_tokens <= 0:
                complete = False
                continue
            cost = _cost_usd(
                str(call.get("model") or ""),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            if cost is None:
                complete = False
            else:
                total += cost
    return total, complete


__all__ = [
    "Stage5BudgetLedger",
    "Stage5CostBudgetExceeded",
    "current_stage5_task_deadline",
    "stage5_task_deadline",
    "successful_call_cost_usd",
]

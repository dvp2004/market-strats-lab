from __future__ import annotations

from dataclasses import dataclass


VALID_SIDES = {"BUY", "SELL"}


@dataclass(frozen=True)
class BrokerOrderIntent:
    symbol: str
    side: str
    quantity: float
    asset_class: str
    strategy_id: str
    portfolio_id: str
    signal_date: str
    expected_execution_date: str
    paper_only: bool = True
    orders_enabled: bool = False
    max_quantity: float = 1.0
    reason: str = ""
    status: str = "created"


@dataclass(frozen=True)
class BrokerFillRecord:
    symbol: str
    side: str
    quantity: float
    asset_class: str
    strategy_id: str
    portfolio_id: str
    signal_date: str
    expected_execution_date: str
    filled_quantity: float
    fill_price: float
    timestamp: str
    paper_only: bool = True
    orders_enabled: bool = False
    max_quantity: float = 1.0
    reason: str = ""
    status: str = "filled"


@dataclass(frozen=True)
class BrokerPositionSnapshot:
    symbol: str
    quantity: float
    asset_class: str
    strategy_id: str
    portfolio_id: str
    timestamp: str
    paper_only: bool = True
    orders_enabled: bool = False
    max_quantity: float = 1.0
    reason: str = ""
    status: str = "observed"


@dataclass(frozen=True)
class ExecutionGuardResult:
    allowed: bool
    status: str
    reason: str
    symbol: str
    side: str
    quantity: float
    max_quantity: float
    paper_only: bool
    orders_enabled: bool


def validate_order_intent(intent: BrokerOrderIntent) -> ExecutionGuardResult:
    reasons: list[str] = []
    side = intent.side.upper()

    if intent.paper_only is not True:
        reasons.append("paper_only_must_be_true")
    if intent.orders_enabled is not False:
        reasons.append("orders_enabled_must_remain_false_by_default")
    if side not in VALID_SIDES:
        reasons.append("side_must_be_buy_or_sell")
    if intent.quantity <= 0:
        reasons.append("quantity_must_be_positive")
    if intent.max_quantity <= 0:
        reasons.append("max_quantity_must_be_positive")
    if intent.quantity > intent.max_quantity:
        reasons.append("quantity_exceeds_max_quantity")

    allowed = not reasons
    return ExecutionGuardResult(
        allowed=allowed,
        status="blocked" if reasons else "validated_paper_intent_only",
        reason="; ".join(reasons) if reasons else "paper_intent_validated_no_order_submission",
        symbol=intent.symbol,
        side=side,
        quantity=intent.quantity,
        max_quantity=intent.max_quantity,
        paper_only=intent.paper_only,
        orders_enabled=intent.orders_enabled,
    )

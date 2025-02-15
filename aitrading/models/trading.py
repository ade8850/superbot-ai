from typing import List, Optional, Dict, Literal, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

from .base import generate_uuid_short
from .orders import Order, OrderCancellation, OrderRole

class Range24h(BaseModel):
    """24-hour price range."""
    high: float
    low: float

class StrategicContext(BaseModel):
    """Strategic context for order evaluation and management."""
    setup_rationale: str = Field(
        description="Original market setup and key technical conditions"
    )
    market_bias: str = Field(
        description="Overall market bias and trend context"
    )
    key_levels: List[float] = Field(
        description="Critical price levels for this setup"
    )
    catalysts: List[str] = Field(
        description="Market conditions or events supporting this setup"
    )
    invalidation_conditions: List[str] = Field(
        description="Specific market conditions that would invalidate this setup"
    )

class OrderExecutionType(str, Enum):
    """Specifies how the order should be executed."""
    IMMEDIATE = "immediate"    # Execute immediately at market
    PASSIVE = "passive"        # Wait for price to reach level
    TRIGGER = "trigger"        # Execute when condition met
    BRACKET = "bracket"        # Part of a bracket order setup

class RiskLevel(str, Enum):
    """Risk level for the order."""
    CRITICAL = "critical"      # Must execute quickly
    NORMAL = "normal"         # Standard execution
    MINIMAL = "minimal"       # Can wait for better price

class PlannedOrder(BaseModel):
    """Complete planned order specification."""
    id: int = Field(default=0, description="Progressive number starting from 1")
    type: Literal["long", "short"]
    symbol: str
    current_price: float
    range_24h: Range24h
    order: Order
    strategic_context: StrategicContext = Field(
        ...,
        description="Strategic context for evaluating order validity"
    )
    order_link_id: Optional[str] = Field(
        None,
        description="Must be in format '{plan_id}-{session_id}-{order_number}' using the provided plan_id and session_id"
    )
    execution_type: OrderExecutionType = Field(
        default=OrderExecutionType.PASSIVE,
        description="How the order should be executed"
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.NORMAL,
        description="Risk level affecting execution priority"
    )

    def set_order_link_id(self, plan_id: str, session_id: str, order_num: int) -> None:
        """Set the order_link_id using plan_id, session_id and order number and update id."""
        if not self.order_link_id:
            self.order_link_id = f"{plan_id}-{session_id}-{order_num}"
            self.id = order_num

class TradingParameters(BaseModel):
    """Input parameters for trading plan generation."""
    symbol: str
    budget: float = Field(ge=10)
    leverage: int = Field(ge=1, le=100)
    stop_loss_config: Optional[Dict] = Field(
        default=None,
        description="Optional configuration for automated stop loss management"
    )

class TradingPlan(BaseModel):
    """Complete trading plan including parameters and planned orders."""
    id: str = Field(
        default_factory=lambda: generate_uuid_short(8),
        description="An eight-character random string"
    )
    session_id: str = Field(
        default_factory=lambda: generate_uuid_short(4),
        description="A four-character session identifier"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parameters: TradingParameters
    cancellations: Optional[List[OrderCancellation]] = Field(
        default=None,
        description="List of orders to be cancelled before executing new orders"
    )
    orders: List[PlannedOrder] = Field(
        default_factory=list,
        description="List of new orders to be placed after any cancellations"
    )
    analysis: str = Field(..., description="Detailed analysis explaining the plan")

    def __init__(self, **data):
        super().__init__(**data)
        # Set order_link_id for each order using plan_id, session_id and order number
        for i, order in enumerate(self.orders, 1):
            order.set_order_link_id(self.id, self.session_id, i)

    @validator('orders')
    def validate_orders(cls, v: List[PlannedOrder], values: Dict[str, Any]) -> List[PlannedOrder]:
        """Validate the complete set of orders in the plan."""
        if not v:
            return v

        # Track order IDs to ensure uniqueness
        order_ids = set()
        order_link_ids = set()

        for order in v:
            # Check ID uniqueness
            if order.id in order_ids:
                raise ValueError(f"Duplicate order ID: {order.id}")
            order_ids.add(order.id)

            # Check order link ID uniqueness
            if order.order_link_id:
                if order.order_link_id in order_link_ids:
                    raise ValueError(f"Duplicate order link ID: {order.order_link_id}")
                order_link_ids.add(order.order_link_id)

        return v

    def get_total_budget_required(self) -> float:
        """Calculate total budget required for all orders."""
        return sum(order.order.entry.budget for order in self.orders)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "plan1234",
                    "session_id": "ab12",
                    "created_at": "2024-01-04T10:00:00Z",
                    "parameters": {
                        "symbol": "BTCUSDT",
                        "budget": 1000.0,
                        "leverage": 2,
                        "stop_loss_config": {
                            "timeframe": "1H",
                            "initial_multiplier": 1.5,
                            "in_profit_multiplier": 2.0
                        }
                    },
                    "cancellations": [
                        {
                            "id": "1234567890",
                            "order_link_id": "old-plan-1",
                            "symbol": "BTCUSDT",
                            "reason": "Order no longer aligns with current market conditions"
                        }
                    ],
                    "orders": [],
                    "analysis": "Detailed market analysis and plan explanation"
                }
            ]
        }
    }

class PlanResponse(BaseModel):
    """Response from AI model including trading plan."""
    plan: TradingPlan = Field(..., description="Complete trading plan with orders")
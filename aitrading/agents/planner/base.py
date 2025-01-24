# aitrading/agents/planner/base.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any


class BaseAIClient(ABC):
    """Base interface for AI model clients."""

    def __init__(self, api_key: str):
        """Initialize the AI client with API key."""
        self.api_key = api_key
        self._active_orders: List[Dict[str, Any]] = []
        self.trading_parameters = None


    def set_trading_parameters(self, parameters: Any) -> None:
        """Set the trading parameters used for validation."""
        self.trading_parameters = parameters

    @abstractmethod
    def generate_strategy(self, system_prompt: str, user_prompt: str, images: List[bytes]) -> Dict[str, Any]:
        """Generate trading plan using the AI model.

        Args:
            system_prompt (str): Framework and rules for analysis
            user_prompt (str): Specific trading parameters and requirements
            images (List[bytes]): Chart images in PNG format

        Returns:
            Dict[str, Any]: Plan response containing:
                - 'plan': Complete trading plan with unique ID and session ID
                - Orders list with progressive numeric IDs
                - Analysis and rationale
        """
        pass

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """Validate response structure and content."""
        try:
            if not isinstance(response, dict):
                raise ValueError("Response must be a dictionary")

            if 'plan' not in response:
                raise ValueError("Response missing 'plan' key")

            # Pre-process the response
            plan = response['plan']

            # Convert analysis object to string if needed
            if isinstance(plan.get('analysis'), dict):
                market_context = plan['analysis'].get('market_context', '')
                reasoning = plan.get('reasoning', '')
                plan['analysis'] = f"{market_context}\n\n{reasoning}"

            # Add defaults if missing
            if 'created_at' not in plan:
                plan['created_at'] = datetime.utcnow().isoformat()

            if 'parameters' not in plan and self.trading_parameters:
                plan['parameters'] = self.trading_parameters

            # Validate using Pydantic model
            from ...models import TradingPlan
            validated_plan = TradingPlan(**plan)
            response['plan'] = validated_plan.model_dump()

            return True

        except Exception as e:
            raise ValueError(f"Response validation failed: {str(e)}")

    def _validate_orders(self, orders: List[Dict[str, Any]]) -> None:
        """Validate new orders structure and IDs."""
        used_ids = set()
        required_order_keys = {
            'id', 'type', 'symbol', 'current_price', 'range_24h',
            'rationale', 'order', 'validity'
        }

        for i, order in enumerate(orders, 1):
            # Check required keys
            if not all(key in order for key in required_order_keys):
                missing = required_order_keys - set(order.keys())
                raise ValueError(f"Order {i} missing keys: {missing}")

            # Validate order ID is numeric and progressive
            order_id = order.get('id')
            if not isinstance(order_id, int) or order_id != i:
                raise ValueError(f"Order {i} should have ID {i}, got {order_id}")

            if order_id in used_ids:
                raise ValueError(f"Duplicate order ID found: {order_id}")

            used_ids.add(order_id)

    def _validate_cancellations(self, cancellations: List[Dict[str, Any]]) -> None:
        """Validate order cancellations structure and format only."""
        if not isinstance(cancellations, list):
            raise ValueError("Cancellations must be a list")

        for i, cancellation in enumerate(cancellations):
            required_keys = {'symbol', 'reason'}
            if not all(key in cancellation for key in required_keys):
                missing = required_keys - set(cancellation.keys())
                raise ValueError(f"Cancellation {i} missing required keys: {missing}")

            # Either id or order_link_id must be present
            if 'id' not in cancellation and 'order_link_id' not in cancellation:
                raise ValueError(f"Cancellation {i} must have either 'id' or 'order_link_id'")

            # Validate types only
            order_id = cancellation.get('id')
            if order_id and not isinstance(order_id, str):
                raise ValueError(f"Cancellation {i} order ID must be a string")

            order_link_id = cancellation.get('order_link_id')
            if order_link_id and not isinstance(order_link_id, str):
                raise ValueError(f"Cancellation {i} order link ID must be a string")

    def set_active_orders(self, orders: List[Dict[str, Any]]) -> None:
        """Set the list of active orders for validation."""
        self._active_orders = orders
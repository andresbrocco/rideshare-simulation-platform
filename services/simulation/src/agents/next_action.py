"""Next action tracking for autonomous agents."""

from dataclasses import dataclass
from enum import Enum


class NextActionType(str, Enum):
    """Types of scheduled actions for agents."""

    # Driver actions
    GO_ONLINE = "go_online"
    GO_OFFLINE = "go_offline"
    ACCEPT_REJECT_OFFER = "accept_reject_offer"

    # Rider actions
    REQUEST_RIDE = "request_ride"
    PATIENCE_TIMEOUT = "patience_timeout"


@dataclass
class NextAction:
    """Represents a scheduled future action for an agent.

    Attributes:
        action_type: The type of action that will occur
        scheduled_at: SimPy simulation time (env.now) when the action will fire
        description: Human-readable description of the action
    """

    action_type: NextActionType
    scheduled_at: float
    description: str

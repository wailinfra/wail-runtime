from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeSignalType(str, Enum):
    FIRST_TOKEN_STALL = "first_token_stall"


@dataclass(slots=True)
class RuntimeSignal:
    signal_type: RuntimeSignalType
    elapsed_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
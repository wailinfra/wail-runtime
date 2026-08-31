import json
from typing import Dict, Any


class TraceSerializer:
    def serialize(self, trace: Dict[str, Any]) -> str:
        return json.dumps(trace, separators=(",", ":"), sort_keys=True)

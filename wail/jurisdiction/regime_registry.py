from __future__ import annotations

from typing import Optional


class RegimeRegistry:

    _active_regime: Optional[str] = None

    @classmethod
    def set_active_regime(cls, regime_id: str) -> None:
        cls._active_regime = regime_id

    @classmethod
    def get_active_regime(cls) -> Optional[str]:
        return cls._active_regime

    @classmethod
    def clear(cls) -> None:
        cls._active_regime = None

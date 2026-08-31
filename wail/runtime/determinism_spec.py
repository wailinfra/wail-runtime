from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Any
import math

DETERMINISM_SPEC_VERSION = 1
FLOAT_PRECISION = 12
ROUNDING_MODE = ROUND_HALF_EVEN

getcontext().prec = 28  


def normalize_float(value: float) -> str:

    if math.isnan(value):
        raise ValueError("NaN not allowed in deterministic artifacts")

    if math.isinf(value):
        raise ValueError("Infinity not allowed in deterministic artifacts")

    decimal_value = Decimal(str(value))

    normalized = decimal_value.quantize(
        Decimal(10) ** -FLOAT_PRECISION,
        rounding=ROUNDING_MODE,
    )

    return format(normalized, "f")


def normalize_timestamp_ms(value: Any) -> int:

    if isinstance(value, float):
        return int(round(value))

    if isinstance(value, int):
        return value

    raise ValueError("Timestamp must be int milliseconds")


def normalize_value(value: Any):

    if isinstance(value, float):
        return normalize_float(value)

    if isinstance(value, dict):
        return {k: normalize_value(value[k]) for k in sorted(value)}

    if isinstance(value, list):
        return [normalize_value(v) for v in value]

    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    raise TypeError(f"Unsupported type for canonicalization: {type(value)}")

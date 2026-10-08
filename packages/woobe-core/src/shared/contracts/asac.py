"""Portable ASaC canonicalization; lifecycle remains owned by Agent/Network."""

from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import math

VERSION = "1.0"


def _canonical(value, depth=0):
    if depth > 128:
        raise ValueError("ASaC nesting exceeds 128")
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, str):
        return ["string", value.encode("utf-8").hex()]
    if isinstance(value, (int, float, Decimal)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("ASaC numbers must be finite")
        text = str(value)
        if len(text) > 4096:
            raise ValueError("ASaC number exceeds canonical bounds")
        decimal = Decimal(text)
        if not decimal.is_finite() or abs(decimal.as_tuple().exponent) > 4096:
            raise ValueError("ASaC number exceeds canonical bounds")
        number = Fraction(decimal)
        return ["number", str(number.numerator), str(number.denominator)]
    if isinstance(value, list):
        return ["array", [_canonical(item, depth + 1) for item in value]]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return ["object", [[key.encode("utf-8").hex(), _canonical(value[key], depth + 1)] for key in sorted(value)]]
    raise ValueError("Unsupported ASaC value")


def asac_digest(scope, value):
    canonical = json.dumps(_canonical(value), separators=(",", ":"), allow_nan=False)
    return "sha256:" + sha256(("woobe-asac@1.0/" + scope + "\n" + canonical).encode("ascii")).hexdigest()

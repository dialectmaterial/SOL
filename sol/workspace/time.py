"""Consistent UTC timestamp parsing across supported Python versions."""
from datetime import datetime, timezone
import re


_FRACTION = re.compile(r"(\d{2}:\d{2}:\d{2})[.,](\d+)")


def parse_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    # Python 3.10 accepts only 3 or 6 fractional digits. Normalize to datetime's
    # microsecond precision, matching newer Python without rewriting stored text.
    normalized = _FRACTION.sub(lambda match: match[1] + "." + match[2][:6].ljust(6, "0"),
                               value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp is not UTC")
    return parsed

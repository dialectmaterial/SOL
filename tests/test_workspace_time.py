"""Workspace dates keep the same precision and UTC rules on Python 3.10+."""
from datetime import datetime, timezone
import unittest

from sol.being.workspace.time import parse_utc_timestamp


class WorkspaceTimeTests(unittest.TestCase):
    def test_fractional_seconds_match_microsecond_precision(self):
        for fraction, expected in (("1", 100000), ("12", 120000), ("123", 123000),
                                   ("1234", 123400), ("12345", 123450),
                                   ("123456", 123456), ("1234567", 123456)):
            for ending in ("Z", "+00:00", "-00:00"):
                value = "2025-01-01T00:00:00." + fraction + ending
                with self.subTest(value=value):
                    self.assertEqual(parse_utc_timestamp(value),
                                     datetime(2025, 1, 1, microsecond=expected, tzinfo=timezone.utc))

    def test_naive_non_utc_and_invalid_values_are_refused(self):
        for value in (None, True, "", "2025-01-01T00:00:00", "2025-01-01T00:00:00+01:00",
                      "2025-99-99T00:00:00Z", "2025-01-01T00:00:00.nanZ"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_utc_timestamp(value)

"""Test del contratto payload e della lista canonica delle feature."""

from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.contracts import (  # noqa: E402
    FEATURE_COUNT,
    FEATURE_NAMES,
    PayloadValidationError,
    validate_inference_payload,
)


def _valid_payload() -> dict[str, list[float]]:
    return {"features": [float(value) for value in range(FEATURE_COUNT)]}


class FeatureContractTests(unittest.TestCase):
    def test_canonical_feature_list(self) -> None:
        self.assertEqual(FEATURE_COUNT, 30)
        self.assertEqual(len(FEATURE_NAMES), 30)
        self.assertEqual(len(set(FEATURE_NAMES)), 30)
        self.assertEqual(FEATURE_NAMES[0], "distanza_pianificata_km")
        self.assertEqual(FEATURE_NAMES[14], "ritardo_medio_rotta_90g_min")
        self.assertEqual(FEATURE_NAMES[-1], "documenti_da_completare")
        self.assertNotIn("record_id", FEATURE_NAMES)
        self.assertNotIn("split", FEATURE_NAMES)
        self.assertNotIn("target", FEATURE_NAMES)

    def test_documentation_table_matches_canonical_order(self) -> None:
        documentation = (
            PROJECT_ROOT / "docs" / "contratto_inferenza.md"
        ).read_text(encoding="utf-8")
        rows = re.findall(
            r"^\| (\d+) \| `([^`]+)` \|$", documentation, re.MULTILINE
        )
        self.assertEqual(len(rows), 30)
        self.assertEqual(
            [int(position) for position, _ in rows], list(range(1, 31))
        )
        self.assertEqual(
            tuple(name for _, name in rows), FEATURE_NAMES
        )

    def test_valid_payload_returns_canonical_order(self) -> None:
        payload = _valid_payload()
        values = validate_inference_payload(payload)
        self.assertEqual(values, tuple(float(v) for v in range(30)))
        self.assertEqual(len(values), 30)

    def test_integer_numbers_are_accepted(self) -> None:
        payload = {"features": list(range(30))}
        self.assertEqual(validate_inference_payload(payload)[0], 0.0)

    def test_missing_features_key_is_rejected(self) -> None:
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload({})
        self.assertEqual(ctx.exception.code, "missing_features")

    def test_extra_keys_are_rejected(self) -> None:
        payload = _valid_payload()
        payload["target"] = [0.0] * 30  # type: ignore[assignment]
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "unexpected_keys")

    def test_payload_must_be_an_object(self) -> None:
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload([0.0] * 30)
        self.assertEqual(ctx.exception.code, "payload_not_object")

    def test_features_must_be_a_list(self) -> None:
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload({"features": tuple(range(30))})
        self.assertEqual(ctx.exception.code, "features_not_list")

    def test_29_values_are_rejected_without_padding(self) -> None:
        payload = {"features": [float(value) for value in range(29)]}
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "wrong_feature_count")
        self.assertIn("29", str(ctx.exception))
        self.assertIn("incomplete", str(ctx.exception))

    def test_31_values_are_rejected(self) -> None:
        payload = {"features": [float(value) for value in range(31)]}
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "wrong_feature_count")

    def test_numeric_string_is_rejected(self) -> None:
        payload = {"features": [str(value) for value in range(30)]}
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "feature_not_numeric")

    def test_boolean_is_rejected(self) -> None:
        payload = _valid_payload()
        payload["features"][0] = True  # type: ignore[assignment]
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "feature_not_numeric")

    def test_null_is_rejected(self) -> None:
        payload = _valid_payload()
        payload["features"][0] = None  # type: ignore[assignment]
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "feature_not_numeric")

    def test_nan_and_infinity_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                payload = _valid_payload()
                payload["features"][0] = value
                with self.assertRaises(PayloadValidationError) as ctx:
                    validate_inference_payload(payload)
                self.assertEqual(ctx.exception.code, "feature_not_finite")

    def test_huge_integer_is_rejected_without_overflow(self) -> None:
        payload = _valid_payload()
        payload["features"][0] = 10**10000  # type: ignore[assignment]
        with self.assertRaises(PayloadValidationError) as ctx:
            validate_inference_payload(payload)
        self.assertEqual(ctx.exception.code, "feature_not_finite")

    def test_validator_does_not_mutate_or_fill(self) -> None:
        payload = {"features": [float(value) for value in range(29)]}
        original = list(payload["features"])
        with self.assertRaises(PayloadValidationError):
            validate_inference_payload(payload)
        self.assertEqual(payload["features"], original)
        self.assertEqual(len(payload["features"]), 29)


if __name__ == "__main__":
    unittest.main()

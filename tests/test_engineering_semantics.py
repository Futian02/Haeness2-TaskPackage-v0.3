import unittest
import json
from pathlib import Path

from orchestration.semantics import (
    EngineeringObservation, EvidenceLink, Hypothesis, InformationGap, ObservationState, extract_observations,
    normalize_measurement, resolve_alias,
)


class EngineeringSemanticsTests(unittest.TestCase):
    def test_unknown_is_not_false_for_unmeasured_thickness(self):
        obs = extract_observations("现场还没测厚")
        wall = next(x for x in obs if x.field == "wall_thinning")
        self.assertEqual(wall.observation_state, ObservationState.unknown)
        self.assertIsNone(wall.value)

    def test_explicit_negative_is_false(self):
        wall = next(x for x in extract_observations("测厚未发现减薄") if x.field == "wall_thinning")
        self.assertEqual(wall.observation_state, ObservationState.observed_false)
        self.assertIs(wall.normalized_value, False)

    def test_explicit_positive_is_true(self):
        wall = next(x for x in extract_observations("测厚发现减薄") if x.field == "wall_thinning")
        self.assertEqual(wall.observation_state, ObservationState.observed_true)

    def test_quantitative_values_preserve_source_span(self):
        obs = extract_observations("水样 pH 5.2，铁离子 4.1 mg/L")
        ph = next(x for x in obs if x.field == "ph")
        iron = next(x for x in obs if x.field == "iron_ion")
        self.assertEqual(ph.normalized_value, 5.2)
        self.assertEqual(iron.normalized_value, 4.1)
        self.assertEqual(iron.raw_span, "铁离子 4.1 mg/L")

    def test_unit_normalization_temperature_fahrenheit(self):
        self.assertEqual(normalize_measurement(212, "°F", "temperature"), (100.0, "°C"))

    def test_unit_normalization_pressure_bar(self):
        self.assertEqual(normalize_measurement(2, "bar", "pressure"), (0.2, "MPa"))

    def test_concentration_alias_units(self):
        self.assertEqual(normalize_measurement(12, "ppm", "chloride"), (12, "mg/L"))

    def test_unknown_units_rejected(self):
        with self.assertRaises(ValueError):
            normalize_measurement(1, "psi", "pressure")

    def test_aliases_are_product_layer_only(self):
        self.assertEqual(resolve_alias("Fe"), ("iron_ion", "mg/L"))
        self.assertEqual(resolve_alias("氯离子"), ("chloride", "mg/L"))
        self.assertIsNone(resolve_alias("碳钢"))

    def test_schema_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            EngineeringObservation(field="pH", raw_span="pH=4", invented_risk="L4")

    def test_ten_natural_language_cases_are_unreviewed_not_gold(self):
        cases = json.loads((Path(__file__).resolve().parents[1] / "evals" / "semantic_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({case["candidate_clause_id"] for case in cases}), 10)
        self.assertTrue(all(case["review_status"] == "draft_needs_review" and case["gold"] is False for case in cases))

    def test_all_four_product_schema_models_validate(self):
        self.assertEqual(EngineeringObservation(field="iron_ion", raw_span="Fe 2 ppm").observation_state, ObservationState.unknown)
        self.assertEqual(EvidenceLink(clause_id="c1").review_status, "draft_needs_review")
        self.assertEqual(Hypothesis(hypothesis_id="h1", label="候选").disposition, "candidate")
        self.assertEqual(InformationGap(field="ph", question="pH?", reason="缺值").priority, "normal")


if __name__ == "__main__":
    unittest.main()

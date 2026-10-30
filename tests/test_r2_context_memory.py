from __future__ import annotations

import threading
import tempfile
import unittest
from pathlib import Path

from backend.context_slots import extract_explicit_context
from backend.conversation_memory import ConversationMemoryService
from backend.store import Store


class R2ContextParserTests(unittest.TestCase):
    def test_at_least_60_real_parser_cases_cover_aliases_unknowns_and_units(self):
        cases: list[tuple[str, str, object]] = []
        materials = [
            ("300系列不锈钢", "300系列不锈钢"), ("300系不锈钢", "300系列不锈钢"),
            ("316L", "奥氏体不锈钢"), ("304", "奥氏体不锈钢"),
            ("碳素钢", "碳钢"), ("Q345R钢板", "Q345R"),
            ("15CrMo钢", "15CrMo"), ("S31608", "06Cr17Ni12Mo2"),
            ("双相型不锈钢", "双相不锈钢"), ("400系不锈钢", "400系列不锈钢"),
            ("low alloy steel", "低合金钢"), ("S30408", "06Cr19Ni10"),
        ]
        media = [
            ("碱式酸性水", ["碱式酸性水"]), ("酸式酸性水", ["酸式酸性水"]),
            ("HCl", ["氯化氢"]), ("湿H2S", ["湿硫化氢"]),
            ("NH4Cl", ["氯化铵"]), ("NH4HS", ["硫氢化铵"]),
            ("CO2", ["二氧化碳"]), ("Cl-", ["氯离子"]),
            ("NaOH", ["氢氧化钠"]), ("胺溶液", ["胺液"]),
            ("含硼工艺液", None), ("未知介质", None),
        ]
        for i, (raw, expected) in enumerate(materials):
            result = extract_explicit_context(f"设备：管道{i}，材质：{raw}")
            cases.append((f"material-{i}", result["values"].get("material"), expected))
        for i, (raw, expected) in enumerate(media):
            result = extract_explicit_context(f"设备：容器{i}，介质：[{raw}]")
            got = result["values"].get("medium")
            if expected is None:
                self.assertNotIn("medium", result["values"], f"medium-{i}")
                self.assertTrue(result["unknown_enum_values"].get("medium"), f"medium-{i}")
                cases.append((f"medium-{i}-unknown-preserved", result["unknown_enum_values"]["medium"][0], raw))
            else:
                cases.append((f"medium-{i}", got, expected))
        temps = [(60, "℃", 60.0), (140, "°F", 60.0), (80, "°C", 80.0),
                 (100, "", 100.0), (-10, "℃", -10.0), (32, "K", None),
                 (212, "℉", 100.0), (50.5, "℃", 50.5), (60, "度C", 60.0),
                 (80, "摄氏度", 80.0), (120, "℃", 120.0), (25, "°C", 25.0)]
        for i, (value, unit, expected) in enumerate(temps):
            raw = f"{value}{unit}"
            result = extract_explicit_context(f"工况温度：{raw}")
            got = result["values"].get("temperature_c")
            if expected is not None:
                cases.append((f"temperature-{i}", got, expected))
            else:
                # Unsupported or unrecognized unit is preserved as raw, not coerced.
                self.assertIn("temperature_c", result["unknown_enum_values"])
                cases.append((f"temperature-{i}-unknown", result["raw_values"]["temperature_c"], raw))
        pressures = [(1, "MPa", 1.0), (1000, "kPa", 1.0), (10, "bar", 1.0),
                     (0.5, "", 0.5), (250, "kPa", 0.25), (2.5, "bar", 0.25),
                     (200000, "Pa", 0.2), (1.2, "MPa", 1.2), (0.08, "", 0.08),
                     (3, "bar", 0.3), (760, "kPa", 0.76), (1.7, "MPa", 1.7)]
        for i, (value, unit, expected) in enumerate(pressures):
            result = extract_explicit_context(f"总压力：{value}{unit}")
            cases.append((f"pressure-{i}", result["values"].get("pressure_mpa"), expected))
        velocities = [(1, "m/s", 1.0), (10, "ft/s", 3.048), (2, "米/秒", 2.0),
                      (0.5, "", 0.5), (3.5, "m/s", 3.5), (5, "ft/s", 1.524),
                      (6, "米/秒", 6.0), (1.25, "m/s", 1.25), (9, "ft/s", 2.7432),
                      (20, "m/s", 20.0), (11, "米/秒", 11.0), (4, "ft/s", 1.2192)]
        for i, (value, unit, expected) in enumerate(velocities):
            result = extract_explicit_context(f"流速：{value}{unit}")
            cases.append((f"flow-{i}", result["values"].get("flow_velocity_m_s"), expected))
        thicknesses = [(1, "mm", 1.0), (2, "cm", 20.0), (3, "毫米", 3.0),
                       (0.5, "cm", 5.0), (8, "mm", 8.0), (1.2, "厘米", 12.0),
                       (10, "mm", 10.0), (3.4, "cm", 34.0), (7, "毫米", 7.0),
                       (2.25, "mm", 2.25), (5, "cm", 50.0), (4, "毫米", 4.0)]
        for i, (value, unit, expected) in enumerate(thicknesses):
            result = extract_explicit_context(f"壁厚：{value}{unit}")
            cases.append((f"thickness-{i}", result["values"].get("thickness_mm"), expected))
        for name, actual, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(actual, expected)
        self.assertGreaterEqual(len(cases), 72)

    def test_case_a_preserves_user_facts_and_exact_source_spans(self):
        q = "设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：[碱式酸性水]，温度：60℃，问题：该减薄属于哪类腐蚀？"
        result = extract_explicit_context(q)
        self.assertEqual(result["values"]["material"], "300系列不锈钢")
        self.assertEqual(result["values"]["medium"], ["碱式酸性水"])
        self.assertEqual(result["values"]["temperature_c"], 60.0)
        for field, raw in (("material", "300系列不锈钢"), ("medium", "[碱式酸性水]"), ("temperature_c", "60℃")):
            span = result["raw_spans"][field]
            self.assertEqual(q[span["start"]:span["end"]], raw)
            self.assertEqual(result["field_details"][field]["confirmation_state"], "USER_ASSERTED")
            self.assertFalse(result["field_details"][field]["independently_verified"])

    def test_case_b_maps_shell_impact_to_component_and_shape_not_equipment_type(self):
        result = extract_explicit_context("设备发生壳体磕碰损伤，什么情况需要停机维修？验收判定标准是什么？")
        self.assertEqual(result["values"]["component"], "壳体")
        self.assertEqual(result["values"]["damage_morphology"], "磕碰损伤")
        self.assertNotIn("equipment", result["values"])
        self.assertNotIn("equipment_type", result["values"])
        self.assertEqual(result["unknown_enum_values"]["equipment_type"], ["壳体"])

    def test_process_wall_and_partial_pressures_are_distinct_and_units_normalized(self):
        result = extract_explicit_context("工况温度：60℃，壁温：80℃，总压力：2 bar，H2S分压：15 kPa")
        self.assertEqual(result["values"]["temperature_c"], 60.0)
        self.assertEqual(result["values"]["wall_temperature_c"], 80.0)
        self.assertEqual(result["values"]["pressure_mpa"], 0.2)
        self.assertEqual(result["values"]["h2s_partial_pressure_mpa"], 0.015)
        self.assertEqual(result["units"]["temperature_c"], "degC")
        self.assertEqual(result["units"]["wall_temperature_c"], "degC")

    def test_unknown_enum_keeps_raw_value_and_span_without_claiming_canonical(self):
        q = "材质：[不在枚举的镍基合金X]，介质：[某新型含硼液]"
        result = extract_explicit_context(q)
        self.assertNotIn("material", result["values"])
        self.assertNotIn("medium", result["values"])
        self.assertEqual(result["unknown_enum_values"]["material"], ["不在枚举的镍基合金X"])
        self.assertEqual(result["unknown_enum_values"]["medium"], ["某新型含硼液"])
        for field in ("material", "medium"):
            span = result["raw_spans"][field]
            self.assertEqual(q[span["start"]:span["end"]], result["raw_values"][field])

    def test_negated_and_uncertain_values_never_become_facts(self):
        result = extract_explicit_context("材质不是碳钢，介质可能为湿H2S，壁温80℃")
        self.assertNotIn("material", result["values"])
        self.assertNotIn("medium", result["values"])
        self.assertEqual(result["values"]["wall_temperature_c"], 80.0)
        self.assertTrue(result["negated_fields"].get("material"))
        self.assertTrue(result["uncertain_fields"].get("medium"))
        self.assertFalse(result["uncertain_fields"].get("wall_temperature_c"))

    def test_explicit_correction_supersedes_prior_and_new_equipment_does_not_inherit(self):
        prior = {"material": "碳钢", "medium": ["湿硫化氢"], "temperature_c": 80}
        corrected = extract_explicit_context("更正：材质不是碳钢，而是316L，温度：60℃", prior_confirmed=prior)
        self.assertEqual(corrected["values"]["material"], "奥氏体不锈钢")
        self.assertEqual(corrected["values"]["temperature_c"], 60.0)
        self.assertTrue(corrected["correction_detected"])
        self.assertTrue(any(row["field"] == "material" and row["resolution"] == "explicit_correction_supersedes_prior"
                            for row in corrected["conflicts"]))
        other = extract_explicit_context("另外一台设备，材质：碳钢", prior_confirmed=prior)
        self.assertTrue(other["new_object_scope"])
        self.assertEqual(other["values"]["material"], "碳钢")
        self.assertNotIn("medium", other["values"])
        self.assertNotIn("temperature_c", other["values"])

    def test_concept_mention_is_not_promoted_to_operating_medium(self):
        result = extract_explicit_context("碱式酸性水中可能发生什么损伤？")
        self.assertNotIn("medium", result["values"])

    def test_structured_form_precedence_keeps_conflict_and_original_raw(self):
        result = extract_explicit_context("材质：碳钢，介质：HCl", {"material": "300系列不锈钢"})
        self.assertEqual(result["values"]["material"], "300系列不锈钢")
        self.assertEqual(result["raw_values"]["material"], "300系列不锈钢")
        self.assertEqual(result["conflicts"][0]["resolution"], "structured_form_wins")


class R2ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r2-context-memory-")
        self.db = Path(self.temp.name) / "isolated.sqlite3"
        self.store = Store(self.db)
        self.cid_a = self.store.create_conversation("A")['id']
        self.cid_b = self.store.create_conversation("B")['id']
        self.memory = ConversationMemoryService(self.store, retain_recent_turns=1,
                                                max_context_chars=500, summary_threshold_chars=1)

    def tearDown(self):
        self.temp.cleanup()

    def test_candidate_fact_cannot_be_read_as_confirmed_user_fact(self):
        assistant = self.store.add_message(self.cid_a, "assistant", "候选：介质可能为湿H2S")
        self.memory.record_candidate_fact(self.cid_a, field="medium", value="湿硫化氢", unit=None,
                                          object_scope="vessel-1", source_message_id=assistant["id"])
        self.assertEqual(self.memory.get_confirmed_facts(self.cid_a), [])
        with self.assertRaises(ValueError):
            self.memory.record_user_confirmed_fact(self.cid_a, field="medium", value="H2S", unit=None,
                                                    object_scope="vessel-1", source_message_id=assistant["id"])

    def test_user_correction_retains_superseded_history_and_active_value(self):
        first = self.store.add_message(self.cid_a, "user", "设备材质：碳钢")
        second = self.store.add_message(self.cid_a, "user", "更正：材质不是碳钢，而是316L")
        old = self.memory.record_user_confirmed_fact(self.cid_a, field="material", value="碳钢", unit=None,
                                                     object_scope="vessel-1", source_message_id=first["id"])
        new = self.memory.record_user_confirmed_fact(self.cid_a, field="material", value="奥氏体不锈钢", unit=None,
                                                     object_scope="vessel-1", source_message_id=second["id"])
        rows = self.store.fact_assertions(self.cid_a)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["confirmation_state"], "superseded")
        self.assertEqual(rows[0]["superseded_by"], new["assertion_id"])
        self.assertEqual(self.memory.get_confirmed_facts(self.cid_a)[0]["assertion_id"], new["assertion_id"])
        self.assertNotEqual(old["assertion_id"], new["assertion_id"])

    def test_two_conversation_ids_are_isolated_in_history_facts_and_summary(self):
        msg_a = self.store.add_message(self.cid_a, "user", "A: 碱式酸性水")
        msg_b = self.store.add_message(self.cid_b, "user", "B: 蒸汽")
        self.memory.record_user_confirmed_fact(self.cid_a, field="medium", value=["碱式酸性水"], unit=None,
                                               object_scope="A", source_message_id=msg_a["id"])
        self.memory.record_user_confirmed_fact(self.cid_b, field="medium", value=["循环水"], unit=None,
                                               object_scope="B", source_message_id=msg_b["id"])
        self.assertEqual(self.memory.get_confirmed_facts(self.cid_a)[0]["value"], ["碱式酸性水"])
        self.assertEqual(self.memory.get_confirmed_facts(self.cid_b)[0]["value"], ["循环水"])
        self.assertNotEqual(self.memory.get_recent_visible_history(self.cid_a), self.memory.get_recent_visible_history(self.cid_b))
        with self.assertRaises(ValueError):
            self.memory.record_user_confirmed_fact(self.cid_a, field="medium", value="leak", unit=None,
                                                    object_scope="A", source_message_id=msg_b["id"])

    def test_summary_is_bounded_mockable_invalid_summary_falls_back_to_raw_history(self):
        rows = []
        for i in range(8):
            rows.append(self.store.add_message(self.cid_a, "user", f"用户输入{i}: " + "工况文本" * 20))
            self.store.add_message(self.cid_a, "assistant", f"答复{i}")
        result = self.memory.propose_summary_if_needed(
            self.cid_a, allow_model=True, summarizer=lambda payload: {"summary": "x", "facts": ["bad"]})
        self.assertEqual(result["status"], "fallback")
        self.assertTrue(result["history"])
        self.assertEqual(result["error_code"], "summary_invalid_or_failed")
        self.assertEqual(len(self.store.messages(self.cid_a)), 16)
        self.assertEqual(self.memory.get_confirmed_facts(self.cid_a), [])

    def test_summary_and_facts_replay_after_sqlite_reopen(self):
        source = self.store.add_message(self.cid_a, "user", "工况：碱式酸性水")
        self.memory.record_user_confirmed_fact(self.cid_a, field="medium", value=["碱式酸性水"], unit=None,
                                               object_scope="tower-A", source_message_id=source["id"])
        for i in range(7):
            self.store.add_message(self.cid_a, "user", f"问{i}" + "字" * 80)
            self.store.add_message(self.cid_a, "assistant", f"答{i}")
        created = self.memory.propose_summary_if_needed(self.cid_a, allow_model=True,
                                                        summarizer=lambda p: "summary hint", model_id="mock")
        self.assertEqual(created["status"], "created")
        store2 = Store(self.db)
        memory2 = ConversationMemoryService(store2, retain_recent_turns=1, max_context_chars=500,
                                            summary_threshold_chars=1)
        self.assertEqual(memory2.get_compacted_summary(self.cid_a)["summary"], "summary hint")
        self.assertEqual(memory2.get_confirmed_facts(self.cid_a)[0]["value"], ["碱式酸性水"])

    def test_schema_migration_is_idempotent_on_isolated_database(self):
        message = self.store.add_message(self.cid_a, "user", "保留消息")
        for _ in range(3):
            reopened = Store(self.db)
            self.assertEqual(reopened.conversation_memory_schema_version, 1)
            self.assertEqual(reopened.messages(self.cid_a)[0]["id"], message["id"])
        with self.store.session() as con:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(integrity, "ok")

    def test_memory_clear_requires_authorization_and_explicit_retention_semantics(self):
        source = self.store.add_message(self.cid_a, "user", "材质：碳钢")
        self.memory.record_user_confirmed_fact(self.cid_a, field="material", value="碳钢", unit=None,
                                               object_scope="vessel", source_message_id=source["id"])
        with self.assertRaises(PermissionError):
            self.memory.clear_memory_records(self.cid_a, retain_audit=True)
        retained = self.memory.clear_memory_records(self.cid_a, authorized=True, retain_audit=True)
        self.assertTrue(retained["audit_retained"])
        self.assertEqual(self.memory.get_confirmed_facts(self.cid_a), [])
        self.assertEqual(len(self.store.fact_assertions(self.cid_a)), 1)
        deleted = self.memory.clear_memory_records(self.cid_a, authorized=True, retain_audit=False)
        self.assertFalse(deleted["audit_retained"])
        self.assertEqual(self.store.fact_assertions(self.cid_a), [])
        self.assertEqual(len(self.store.messages(self.cid_a)), 1)  # this API never purges the conversation

    def test_concurrent_fact_writes_keep_conversation_boundaries(self):
        failures: list[str] = []
        barrier = threading.Barrier(2)

        def writer(cid: str, prefix: str):
            try:
                local_store = Store(self.db)
                local_memory = ConversationMemoryService(local_store)
                barrier.wait(timeout=5)
                for index in range(12):
                    msg = local_store.add_message(cid, "user", f"{prefix}-{index}")
                    local_memory.record_user_confirmed_fact(cid, field="tag", value=f"{prefix}-{index}",
                                                            unit=None, object_scope=prefix,
                                                            source_message_id=msg["id"])
            except Exception as exc:  # captured and asserted in parent thread
                failures.append(repr(exc))

        threads = [threading.Thread(target=writer, args=(self.cid_a, "A")),
                   threading.Thread(target=writer, args=(self.cid_b, "B"))]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        facts_a, facts_b = self.store.fact_assertions(self.cid_a), self.store.fact_assertions(self.cid_b)
        self.assertEqual(len(facts_a), 12)
        self.assertEqual(len(facts_b), 12)
        self.assertTrue(all(row["object_scope"] == "A" for row in facts_a))
        self.assertTrue(all(row["object_scope"] == "B" for row in facts_b))


if __name__ == "__main__":
    unittest.main()

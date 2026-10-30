"""S2.5 killable tool worker contract; only original read-only teacher tools."""
from __future__ import annotations

import unittest
from orchestration.agentic_v2 import AgenticV2Candidate


class IsolatedTeacherToolTests(unittest.TestCase):
    def test_real_teacher_tool_call_is_json_serialized_in_worker(self):
        candidate = AgenticV2Candidate(tool_timeout_seconds=8.0)
        result = candidate._invoke("standard_clause_search",
                                   {"keyword": "氯化铵", "top_k": 2}, max_attempts=1)
        self.assertEqual(result["status"], "returned", result)
        self.assertEqual(result["attempts"], 1)
        envelope = result["envelope"]
        self.assertEqual(set(envelope),
                         {"status", "in_domain", "result", "source", "message"})
        self.assertTrue(envelope["source"], "expected a real official clause reference")

    def test_short_deadline_terminates_isolated_process_attempt(self):
        candidate = AgenticV2Candidate(tool_timeout_seconds=.001)
        result = candidate._invoke("standard_clause_search",
                                   {"keyword": "氯化铵", "top_k": 2}, max_attempts=1)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempts"], 1)
        self.assertIn("deadline exceeded", result["error"])

    def test_unregistered_tool_name_does_not_spawn_worker(self):
        candidate = AgenticV2Candidate(tool_timeout_seconds=8.0)
        result = candidate._invoke("execute_unsafe_command",
                                   {"whatever": "value"}, max_attempts=1)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempts"], 0)


if __name__ == "__main__":
    unittest.main()

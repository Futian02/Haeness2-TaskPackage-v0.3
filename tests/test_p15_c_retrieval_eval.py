import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p15_c_retrieval_eval",ROOT/"scripts/p15_c_retrieval_eval.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class RetrievalEvalTests(unittest.TestCase):
    def test_minimum_question_count_and_priority_topics(self):
        self.assertGreaterEqual(len(module.CASES),40)
        joined="\n".join(q for _,_,q,_ in module.CASES)
        for token in ("面积后果","5.23","5.6","6.7","总操作压力","9999"):
            self.assertIn(token,joined)

    def test_all_question_ids_unique_and_gold_or_explicit_no_gold(self):
        ids=[x[0] for x in module.CASES]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(x[3]=="__NO_GOLD__" or x[3] for x in module.CASES))
        formal_ids=set(module.tools.load_clauses()[0])
        states={"FORMAL_CLAUSE_ID_LINKED_UNREVIEWED" if x[3]!="__NO_GOLD__" and set(x[3].split("|")).issubset(formal_ids) else "NO_GOLD_UNJUDGED" if x[3]=="__NO_GOLD__" else "GOLD_ID_NOT_IN_ACTIVE_CORPUS" for x in module.CASES}
        self.assertGreaterEqual(len(states),2)

    def test_condition_probes_include_known_523_false_exclusion_risk(self):
        probe=next(x for x in module.FILTER_PROBES if x["case_id"]=="523_phase_window_80c")
        response=module.tools.damage_mechanism_query(probe["material"],probe["medium"],probe["temperature_c"],"管道")
        result=response.get("result",{})
        self.assertEqual(response.get("status"),"out_of_domain")
        self.assertNotIn(probe["target"],[r.get("clause_id") for r in result.get("mechanisms",[])])
        self.assertEqual(probe["expected"],"not_hard_excluded_by_local_phase_window")

if __name__=="__main__": unittest.main()

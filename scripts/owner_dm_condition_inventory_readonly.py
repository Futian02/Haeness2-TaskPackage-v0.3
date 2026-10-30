"""Read-only Owner inventory of mechanism applicability in official JSONL.
Never edits teacher data. Counts are data completeness, not E2/E3 correctness.
"""
from __future__ import annotations
from pathlib import Path
import json,collections
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"upstream/05_提交区/clauses.jsonl"
def main():
    rows=[json.loads(s)for s in SOURCE.read_text(encoding="utf-8").splitlines()if s.strip()]
    rows=[r for r in rows if r.get("knowledge_type")=="damage_mechanism"]
    cond_fields=["material","medium","equipment_type","temperature_c","pressure_mpa","other"]
    details=["description","morphology","affected_materials","influencing_factors","susceptible_locations","prevention","detection_methods","related_damages"]
    def nonempty(x):
        if x is None or x=="":return False
        if isinstance(x,list):return any(nonempty(i) for i in x)
        if isinstance(x,dict):return any(nonempty(i) for i in x.values())
        return True
    result={
      "records":len(rows),
      "condition_nonempty":{f:sum(nonempty(r.get("applicable_conditions",{}).get(f)) for r in rows) for f in cond_fields},
      "detail_nonempty":{f:sum(nonempty(r.get("mechanism_detail",{}).get(f)) for r in rows) for f in details},
      "exact_medium_enumerated":sum(bool(r.get("applicable_conditions",{}).get("medium")) for r in rows),
      "missing_medium_but_evidence_text":sum(not r.get("applicable_conditions",{}).get("medium") and nonempty(r.get("mechanism_detail",{}).get("influencing_factors")) for r in rows),
      "empty_medium_samples":[{
        "id":r["clause_id"],"title":r["title"],
        "aff_material":(r.get("mechanism_detail",{}).get("affected_materials") or [])[:2],
        "influencing":(r.get("mechanism_detail",{}).get("influencing_factors") or [])[:2],
        "other":str(r.get("applicable_conditions",{}).get("other") or "")[:140]
      }for r in rows if not nonempty(r.get("applicable_conditions",{}).get("medium"))][:12],
      "without_verifier":sum(not r.get("verified_by") for r in rows),
      "standard_codes":dict(collections.Counter(r.get("standard_code") for r in rows))
    }
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()

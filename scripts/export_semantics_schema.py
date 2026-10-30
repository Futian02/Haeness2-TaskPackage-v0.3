"""Export the product-only Pydantic contracts for review."""
import json
from pathlib import Path

from orchestration.semantics import EngineeringObservation, EvidenceLink, Hypothesis, InformationGap

ROOT = Path(__file__).resolve().parents[1]
MODELS = {m.__name__: m for m in (EngineeringObservation, Hypothesis, EvidenceLink, InformationGap)}
schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Haeness2 R1 product engineering semantics",
          "description": "Product-layer draft contracts; not a teacher tool schema.",
          "$defs": {name: model.model_json_schema(ref_template="#/$defs/{model}") for name, model in MODELS.items()}}
out = ROOT / "docs" / "audits" / "R1_ENGINEERING_SEMANTICS_SCHEMA.json"
out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)} defs={len(MODELS)}")

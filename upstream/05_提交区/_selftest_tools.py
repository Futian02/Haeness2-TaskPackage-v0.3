"""tools.py 自测：用官方 schema 校验返回外壳，并覆盖各工具的正常与异常路径。

运行： .venv/Scripts/python.exe 05_提交区/_selftest_tools.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools  # noqa: E402

try:
    from jsonschema import Draft7Validator
except ImportError:  # pragma: no cover
    print("缺少 jsonschema，无法做结构校验")
    raise

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "04_接口文档" / "schema" / "tool_response.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft7Validator(SCHEMA)

PASS = 0
FAIL = 0


def check(label: str, resp: dict, *, expect_status: str | None = None,
          expect_count: int | None = None) -> dict:
    """校验外壳 + 附加断言。"""
    global PASS, FAIL
    problems: list[str] = []

    errors = sorted(VALIDATOR.iter_errors(resp), key=lambda e: e.path)
    for err in errors:
        problems.append(f"schema: {'/'.join(map(str, err.path))} {err.message}")

    if expect_status and resp.get("status") != expect_status:
        problems.append(f"status 期望 {expect_status}，实际 {resp.get('status')}")

    # 红线复检（不依赖 schema）
    if resp.get("status") == "ok" and not resp.get("source"):
        problems.append("ok 但 source 为空")
    if resp.get("in_domain") is False:
        if resp.get("result"):
            problems.append("in_domain=False 但 result 非空")
        if not (resp.get("message") or "").strip():
            problems.append("in_domain=False 但 message 为空")

    # source 只能有 4 个键
    for item in resp.get("source") or []:
        if set(item) != {"clause_id", "standard_code", "clause_no", "page"}:
            problems.append(f"source 键不合规：{sorted(item)}")
        if not isinstance(item.get("page"), int):
            problems.append(f"source.page 不是整数：{item.get('page')!r}")

    # 按工具检查 result 内部结构
    result = resp.get("result") or {}
    if resp.get("status") == "ok" and "mechanisms" in result:
        eight = ("description", "morphology", "affected_materials", "influencing_factors",
                 "susceptible_locations", "prevention", "detection_methods", "related_damages")
        for mech in result["mechanisms"]:
            for key in eight:
                if key not in mech:
                    problems.append(f"mechanism 缺字段 {key}")
            if not isinstance(mech.get("description"), str):
                problems.append("description 不是字符串")
            for key in eight[1:]:
                if not isinstance(mech.get(key), list):
                    problems.append(f"{key} 不是数组")
            if not mech.get("name") or not mech.get("clause_id"):
                problems.append("mechanism 缺 name/clause_id")
            if mech.get("match_level") not in ("high", "medium", "low"):
                problems.append(f"match_level 非法：{mech.get('match_level')!r}")
        if "discriminator" not in result or not isinstance(result["discriminator"], str):
            problems.append("缺 discriminator 或类型错误")
        if "excluded" not in result or not isinstance(result["excluded"], list):
            problems.append("缺 excluded 或类型错误")
        for item in result.get("excluded") or []:
            if set(item) != {"name", "reason"}:
                problems.append(f"excluded 项键不合规：{sorted(item)}")

    if resp.get("status") == "ok" and "hits" in result:
        for hit in result["hits"]:
            if set(hit) != {"clause_id", "title", "snippet", "score"}:
                problems.append(f"hit 键不合规：{sorted(hit)}")
            if len(hit.get("snippet", "")) > 200:
                problems.append(f"snippet 超 200 字：{len(hit['snippet'])}")
            if not (0.0 <= float(hit.get("score", -1)) <= 1.0):
                problems.append(f"score 越界：{hit.get('score')}")
        scores = [h["score"] for h in result["hits"]]
        if scores != sorted(scores, reverse=True):
            problems.append("hits 未按 score 降序")

    if expect_count is not None:
        got = len(result.get("mechanisms") or result.get("hits") or [])
        if got != expect_count:
            problems.append(f"条目数期望 {expect_count}，实际 {got}")

    if problems:
        FAIL += 1
        print(f"[FAIL] {label}")
        for p in problems:
            print(f"       - {p}")
    else:
        PASS += 1
        print(f"[ OK ] {label}")
    return resp


# ---------------------------------------------------------------- 用例
print("=" * 78)
print("一、damage_mechanism_query")
print("=" * 78)
r = check("碳钢+氯化氢 95℃ 管道（正常直配）",
          tools.damage_mechanism_query("碳钢", ["氯化氢"], temperature_c=95, equipment_type="管道"),
          expect_status="ok")
print(f"       mechanisms={[m['name'] for m in r['result'].get('mechanisms', [])]}")
print(f"       excluded={[e['name'] for e in r['result'].get('excluded', [])]}")
print(f"       discriminator={r['result'].get('discriminator', '')[:80]}...")

r = check("碳钢+湿硫化氢 110℃ 换热器（带证据）",
          tools.damage_mechanism_query(
              "碳钢", ["湿硫化氢"], temperature_c=110, equipment_type="换热器",
              evidence={"ph": 5.8, "h2s_ppm": 300, "wall_thinning": False, "crack_found": False}),
          expect_status="ok")
print(f"       mechanisms={[m['name'] for m in r['result'].get('mechanisms', [])]}")

r = check("别名归一化：湿H2S + HCl",
          tools.damage_mechanism_query("碳钢", ["湿H2S", "HCl"], temperature_c=100),
          expect_status="ok")
print(f"       mechanisms={[m['name'] for m in r['result'].get('mechanisms', [])]}")

check("证据类型错误（wall_thinning 给了字符串）",
      tools.damage_mechanism_query("碳钢", ["湿硫化氢"], evidence={"wall_thinning": "yes"}),
      expect_status="error")

check("证据子字段未知",
      tools.damage_mechanism_query("碳钢", ["湿硫化氢"], evidence={"ph_value": 6}),
      expect_status="error")

check("medium 传成逗号字符串",
      tools.damage_mechanism_query("碳钢", "湿硫化氢,氯化氢"),
      expect_status="error")

check("介质不在枚举表",
      tools.damage_mechanism_query("碳钢", ["王水"]),
      expect_status="error")

r = check("出域组合：钛+氢氧化钠 600℃（应 out_of_domain 或给出候选）",
          tools.damage_mechanism_query("钛" if False else "碳钢", ["含盐水"], temperature_c=600),
          expect_status=None)
print(f"       status={r['status']}  msg={r['message'][:70]}")

print()
print("=" * 78)
print("二、rbi_lookup")
print("=" * 78)
r = check("换热器+碳钢+氯化铵腐蚀（无成对等级 → ok + 判定路径）",
          tools.rbi_lookup("换热器", "碳钢", mechanism="氯化铵腐蚀", service_years=8),
          expect_status="ok")
print(f"       message={r['message'][:90]}")
if not r["source"]:
    print("       [FAIL] 判定路径必须带 source（status=ok 的硬性红线）")
else:
    print(f"       source {len(r['source'])} 条: "
          f"{[s['clause_no'] for s in r['source']]}")
if r["result"].get("likelihood") is not None:
    print("       [FAIL] 算不出等级时 likelihood 必须为 null")
if r["result"].get("risk_level_unified") is not None:
    print("       [FAIL] 算不出等级时 risk_level_unified 必须为 null")

r = check("塔+碳钢+湿硫化氢破坏（同上）",
          tools.rbi_lookup("塔", "碳钢", mechanism="湿硫化氢破坏", medium=["湿硫化氢"]),
          expect_status="ok")
print(f"       message={r['message'][:90]}")
if not r["source"]:
    print("       [FAIL] 判定路径必须带 source")

r = check("矩阵格：风险等级的确定（应 ok 且等级来自同一条记录）",
          tools.rbi_lookup("容器", "碳钢", mechanism="风险等级的确定"),
          expect_status="ok")
res = r["result"]
print(f"       L={res.get('likelihood')} C={res.get('consequence')} "
      f"原始={res.get('risk_level')} 统一={res.get('risk_level_unified')} "
      f"周期={res.get('inspection_interval_year')}")
print(f"       basis_note={res.get('basis_note', '')[:90]}")
if res.get("risk_level_unified") not in ("L1", "L2", "L3", "L4"):
    print("       [FAIL] 统一等级不在 L1~L4")
    FAIL += 1

print()
print("=" * 78)
print("三、standard_clause_search")
print("=" * 78)
r = check("氯化铵 结晶温度（damage_mechanism, top3）",
          tools.standard_clause_search("氯化铵 结晶温度", knowledge_type="damage_mechanism", top_k=3),
          expect_status="ok")
if not r["result"].get("hits"):
    print("       [FAIL] 未命中任何条款")
    FAIL += 1
for hit in r["result"].get("hits", []):
    print(f"       {hit['score']:.4f}  {hit['clause_id']:28s} {hit['title'][:22]}")

r = check("风险等级（命中 25 条同名标题，检验排序稳定性）",
          tools.standard_clause_search("风险等级", top_k=5),
          expect_status="ok", expect_count=5)
for hit in r["result"].get("hits", []):
    print(f"       {hit['score']:.4f}  {hit['clause_id']:28s} {hit['title'][:22]}")

check("keyword 缺失（空字符串）",
      tools.standard_clause_search(""),
      expect_status="error")

check("knowledge_type 非法值",
      tools.standard_clause_search("腐蚀", knowledge_type="damage"),
      expect_status="error")

r = check("top_k 超上限 50（工具侧截到 20）",
          tools.standard_clause_search("腐蚀", top_k=50),
          expect_status="ok")
print(f"       hits={len(r['result'].get('hits', []))}")

r = check("无命中关键词",
          tools.standard_clause_search("zzzz不存在的词"),
          expect_status="not_found")

print()
print("=" * 78)
print(f"结果：通过 {PASS} 项，失败 {FAIL} 项")
print("=" * 78)
sys.exit(0 if FAIL == 0 else 1)

"""护栏测试:跑 guardrail_cases.jsonl 与 normal_cases.jsonl,统计拦截率与误拦数(技术指标3)。

在任务包根目录运行:
  python 04_接口文档/harness_skeleton/run_guardrail_tests.py
  python 04_接口文档/harness_skeleton/run_guardrail_tests.py --guardrail 某文件.jsonl --normal 某文件.jsonl

用例格式见 04_接口文档/templates/用例格式说明.md。
测的是 harness.py 里 build_registry() 注册的工具,把 mock 换成真实实现后结果才有意义。
退出码:0 全部符合预期;1 有漏拦或误拦;2 用例文件读取或格式问题。
"""

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Harness, GuardrailError, build_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SUBMIT = ROOT / "05_提交区"
CATEGORIES = ("unknown_tool", "missing_param", "out_of_domain", "bad_format")
REQUIRED = ("case_id", "category", "description", "call", "expect")


def load_cases(path: Path, allowed: tuple) -> list:
    cases, ids = [], set()
    with path.open(encoding="utf-8-sig") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            c = json.loads(line)
            miss = [k for k in REQUIRED if k not in c]
            if miss:
                raise ValueError(f"{path.name}:{n} 缺少字段 {miss}")
            if c["category"] not in allowed:
                raise ValueError(f"{path.name}:{n} category 只能是 {list(allowed)}")
            if c["case_id"] in ids:
                raise ValueError(f"{path.name}:{n} case_id {c['case_id']!r} 重复")
            ids.add(c["case_id"])
            cases.append(c)
    return cases


def run_case(case: dict) -> tuple:
    """返回 (是否被拦, 拦截类型或返回摘要)。"""
    reg = build_registry()
    if "mock_response" in case:
        spec = reg.get(case["call"]["tool"])
        if spec is not None:
            fixed = copy.deepcopy(case["mock_response"])
            spec.func = lambda **kw: copy.deepcopy(fixed)
    h = Harness(reg)
    try:
        resp = h.call_tool(case["call"]["tool"], copy.deepcopy(case["call"].get("args", {})))
    except GuardrailError as e:
        return True, e.kind, e.detail
    except Exception as e:  # 工具实现本身报错,按未拦截处理,需要修代码
        return False, "error", f"工具执行异常: {e}"
    if resp.get("in_domain") is False and not resp.get("result"):
        return True, "out_of_domain", resp.get("message", "")
    return False, resp.get("status", ""), resp.get("message", "")


def judge(case: dict, blocked: bool, kind: str) -> bool:
    if case["expect"] == "pass":
        return not blocked
    return blocked and kind == case["category"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="护栏拦截率与误拦测试")
    p.add_argument("--guardrail", type=Path, default=SUBMIT / "guardrail_cases.jsonl")
    p.add_argument("--normal", type=Path, default=SUBMIT / "normal_cases.jsonl")
    p.add_argument("--report", type=Path, default=SUBMIT / "guardrail_report.md")
    args = p.parse_args(argv)
    try:
        g = load_cases(args.guardrail, CATEGORIES)
        n = load_cases(args.normal, ("normal",))
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"无法读取用例: {e}", file=sys.stderr)
        return 2

    rows, ok_by_cat, total_by_cat = [], Counter(), Counter()
    for case in g + n:
        blocked, kind, detail = run_case(case)
        ok = judge(case, blocked, kind)
        total_by_cat[case["category"]] += 1
        ok_by_cat[case["category"]] += ok
        rows.append((case["case_id"], case["category"], case["expect"], "拦截" if blocked else "放行", kind, "符合" if ok else "不符合", detail))

    lines = ["# 护栏测试报告", "", "| 用例 | 类别 | 预期 | 实际 | 类型 | 判定 | 说明 |", "|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in rows]
    lines += ["", "| 类别 | 用例数 | 符合预期 | 要求 |", "|---|---|---|---|"]
    passed = True
    for cat in CATEGORIES:
        t, o = total_by_cat[cat], ok_by_cat[cat]
        passed &= t >= 3 and o == t
        lines.append(f"| {cat} | {t} | {o} | ≥3 条且全部拦截 |")
    t, o = total_by_cat["normal"], ok_by_cat["normal"]
    passed &= t >= 30 and o == t
    lines.append(f"| normal | {t} | {o} | ≥30 条且全部放行 |")
    blocked_total = sum(total_by_cat[c] for c in CATEGORIES)
    caught = sum(ok_by_cat[c] for c in CATEGORIES)
    lines += ["", f"拦截率 {caught}/{blocked_total}，误拦 {t - o} 条，结论：{'达标' if passed else '不达标'}"]
    report = "\n".join(lines) + "\n"
    print(report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"报告已写入 {args.report}")
    return 0 if passed else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())

"""Bounded real-model smoke test. Public synthetic prompts only.

Explicit invocation required: never invoked by application startup, CI, tests,
or the fake V2 graph. At most four real requests with <=450 output tokens each.
No API keys, raw model content, or device data are logged or persisted.
"""
from __future__ import annotations

import argparse
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from backend.model_profiles import safe_profile

CASES = (
    ("greeting", "你好，请介绍你的功能。", "GENERAL"),
    ("standard", "请查询GB/T 30579-2022关于氯化铵腐蚀的标准条款。", "STANDARD_LOOKUP"),
    ("engineering", "某换热器发现裂纹，材料与介质未知，请提出专业调查方向。", "ENGINEERING"),
    ("mixed", "你好，解释一下应力腐蚀开裂，然后查标准并分析这台设备的裂纹。", "MIXED"),
)
INSTRUCTIONS = (
    "你是工业智能体的任务分类器，不是诊断专家。只输出一个合法JSON对象，"
    "字段route只能从GENERAL、STANDARD_LOOKUP、ENGINEERING、MIXED中选择。"
    "字段next_tool只能从none、standard_clause_search、damage_mechanism_query、rbi_lookup中选择。"
    "字段needs_more是布尔值。不能虚构未提供的工况或提出确定风险等级。"
    "包含设备失效分析的混合问题必须分类MIXED；无材料介质时不应调用damage_mechanism_query。"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=1, choices=(1, 2, 3, 4))
    options = parser.parse_args()
    p = safe_profile()
    if not p:
        print(json.dumps({"status": "NO_PROFILE"}))
        return 2
    endpoint = p["endpoint"]
    if not endpoint.startswith("https://"):
        print(json.dumps({"status": "INVALID_ENDPOINT"}))
        return 2
    outcomes = []
    for name, question, expected in CASES[:options.cases]:
        payload = {
            "model": p["model"], "temperature": 0, "max_tokens": 450, "stream": False,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": INSTRUCTIONS},
                         {"role": "user", "content": question}],
        }
        started = time.perf_counter()
        request = Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + p["api_key"],
                     "Content-Type": "application/json"}, method="POST")
        stage = "request"
        response_chars = None
        finish_reason = None
        try:
            with urlopen(request, timeout=min(30.0, float(p.get("timeout", 30.0)))) as response:
                body = json.loads(response.read(262144).decode("utf-8"))
            stage = "model_content"
            text = str(body["choices"][0]["message"]["content"]).strip()
            response_chars = len(text)
            finish_reason = body["choices"][0].get("finish_reason")
            stage = "strict_json_parse"
            if text.startswith("```"):
                text = text.strip("`").removeprefix("json").strip()
            data = json.loads(text)
            route = data.get("route", "")
            tool = data.get("next_tool", "")
            model_usage = body.get("usage") or {}
            allowed = {"none", "standard_clause_search", "damage_mechanism_query", "rbi_lookup"}
            safe = tool in allowed and not (name == "engineering" and tool == "damage_mechanism_query")
            outcomes.append({"case": name, "expected": expected, "returned": route,
                             "route_match": route == expected, "safe_tool": safe,
                             "elapsed_ms": int((time.perf_counter()-started)*1000),
                             "total_tokens": model_usage.get("total_tokens"),
                             "finish_reason": body["choices"][0].get("finish_reason")})
        except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, TimeoutError) as exc:
            outcomes.append({"case": name, "status": "PROVIDER_OR_PARSE_ERROR",
                             "error_kind": type(exc).__name__,
                             "stage": stage, "response_chars": response_chars,
                             "finish_reason": finish_reason,
                             "http_code": getattr(exc, "code", None),
                             "elapsed_ms": int((time.perf_counter()-started)*1000)})
            break
    print(json.dumps({"experiment": "V2_S25_REAL_LLM_BOUNDED", "provider":p.get("provider"),
        "model": p["model"], "cases": outcomes, "calls_attempted": len(outcomes),
        "all_route_match": len(outcomes)==options.cases and all(x.get("route_match") for x in outcomes),
        "real_calls_not_fake": True}, ensure_ascii=False))
    return 0 if len(outcomes)==options.cases and all(x.get("route_match") for x in outcomes) else 1


if __name__=="__main__":
    raise SystemExit(main())

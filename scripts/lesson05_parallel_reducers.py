"""Lesson 05: a REAL LangGraph parallel fan-out / reducer / merge exercise.

Read-only local teaching demo. No teacher tool calls, no LLM, no PDF/Excel writes.
Run with .venv-langgraph:
    ./.venv-langgraph/Scripts/python.exe -B -m scripts.lesson05_parallel_reducers
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END


class BadState(TypedDict):
    observation: str
    notes: list[str]


def search_bad(_: BadState):
    return {"notes": ["检索：找到一个候选条款"]}


def skeptic_bad(_: BadState):
    return {"notes": ["反证：尚未取得设备壁厚数据"]}


def build_bad():
    graph = StateGraph(BadState)
    graph.add_node("search", search_bad)
    graph.add_node("skeptic", skeptic_bad)
    graph.add_edge(START, "search")
    graph.add_edge(START, "skeptic")
    return graph.compile()


class Evidence(TypedDict):
    id: str
    agent: str
    statement: str
    source_id: str | None


class State(TypedDict):
    observation: str
    candidates: Annotated[list[Evidence], operator.add]
    verdicts: list[str]
    trace: Annotated[list[str], operator.add]


def source_agent(_: State):
    # "S1" is deliberately a fixture, NOT a verified GB/T clause.
    return {"candidates": [
        {"id": "hyp-1", "agent": "EvidenceAgent",
         "statement": "检测现象与腐蚀候选有关（教学假设）", "source_id": "TEST-CLAUSE-S1"}
    ], "trace": ["EvidenceAgent 完成候选查找"]}


def skeptical_agent(_: State):
    # It reads only the independent observation, not EvidenceAgent's text.
    return {"candidates": [
        {"id": "hyp-1", "agent": "Skeptic",
         "statement": "未测厚，不能证明设备实际减薄", "source_id": None}
    ], "trace": ["Skeptic 从原始观测发现证据缺口"]}


def merge(state: State):
    # Reducer can combine contributions; semantic checking belongs to this node.
    records = sorted(state["candidates"], key=lambda x: (x["id"], x["agent"]))
    independent = {x["agent"] for x in records}
    if "EvidenceAgent" not in independent or "Skeptic" not in independent:
        raise AssertionError("Parallel review was not independent")
    return {"verdicts": ["候选待核：不生成设备风险等级", "测厚状态=unknown"],
            "trace": ["merge 对同一hyp-1的两种审查证据进行分组"]}


def build_good():
    graph = StateGraph(State)
    graph.add_node("evidence", source_agent)
    graph.add_node("skeptic", skeptical_agent)
    graph.add_node("merge", merge)
    graph.add_edge(START, "evidence")
    graph.add_edge(START, "skeptic")
    graph.add_edge(["evidence", "skeptic"], "merge")
    graph.add_edge("merge", END)
    return graph.compile()


def main():
    print("=== WITHOUT REDUCER ===")
    try:
        build_bad().invoke({"observation": "塔顶铁离子升高，尚未测厚", "notes": []})
    except Exception as exc:
        print("EXPECTED_CONFLICT:", type(exc).__name__, str(exc).splitlines()[0][:240])
        assert "InvalidUpdateError" in type(exc).__name__
    else:
        raise AssertionError("Expected concurrent writes conflict; engine behavior changed")

    print("=== WITH REDUCER + SEMANTIC MERGE ===")
    app = build_good()
    initial: State = {"observation": "塔顶铁离子升高，尚未测厚",
                      "candidates": [], "verdicts": [], "trace": []}
    result = app.invoke(initial)
    print("CANDIDATES:", [(r["id"], r["agent"]) for r in result["candidates"]])
    print("VERDICTS:", result["verdicts"])
    print("TRACE:", result["trace"])
    assert len(result["candidates"]) == 2
    assert result["verdicts"][1] == "测厚状态=unknown"
    assert len(result["trace"]) == 3
    print("LESSON_05_PARALLEL_REDUCER_PASS")


if __name__ == "__main__":
    main()

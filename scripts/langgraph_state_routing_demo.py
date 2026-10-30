"""LangGraph study example. No LLM calls, no source-data mutation.

Run: python -B -m scripts.langgraph_state_routing_demo
Learns: State, Node, Edge, conditional routing, reducer, and stream updates.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    question: str
    material: str
    medium: list[str]
    route: str
    audit_events: Annotated[list[str], operator.add]
    answer: str


def supervisor(state: State) -> dict:
    needs_context = not state["material"] or not state["medium"]
    return {
        "route": "need_context" if needs_context else "lookup",
        "audit_events": [f"supervisor.route={'need_context' if needs_context else 'lookup'}"],
    }


def dispatch(state: State) -> Literal["request_context", "retrieve"]:
    return "request_context" if state["route"] == "need_context" else "retrieve"


def request_context(state: State) -> dict:
    return {
        "answer": "需要先补充材质和介质，不能直接确定机理或RBI等级。",
        "audit_events": ["request_context (no tool call)"],
    }


def retrieve(state: State) -> dict:
    # This deliberately does NOT manufacture a standard citation.
    return {"audit_events": ["retrieve (teaching placeholder; no actual standards queried)"]}


def reporter(state: State) -> dict:
    return {
        "answer": "结构信息已具备；实际研判需调用官方三工具并核验来源。",
        "audit_events": ["reporter (non-diagnostic demo)"],
    }


def build():
    g = StateGraph(State)
    g.add_node("supervisor", supervisor)
    g.add_node("request_context", request_context)
    g.add_node("retrieve", retrieve)
    g.add_node("reporter", reporter)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", dispatch)
    g.add_edge("request_context", END)
    g.add_edge("retrieve", "reporter")
    g.add_edge("reporter", END)
    return g.compile()


def main():
    graph = build()
    for label, material, medium in (
        ("missing_context", "", []),
        ("has_context", "碳钢", ["氯化氢"]),
    ):
        print(f"CASE {label}")
        state: State = {
            "question": "塔顶铁离子升高、尚未测厚",
            "material": material,
            "medium": medium,
            "route": "",
            "audit_events": [],
            "answer": "",
        }
        for patch in graph.stream(state, stream_mode="updates"):
            print("PATCH", patch)
        finished = graph.invoke(state)
        print("EVENTS", finished["audit_events"])
        print("ANSWER", finished["answer"])
        assert len(finished["audit_events"]) == (2 if not material else 3)
    print("STUDY_DEMO_PASS")


if __name__ == "__main__":
    main()

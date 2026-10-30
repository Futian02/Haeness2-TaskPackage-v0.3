"""First usable Gradio interface. Run: python -m app.web

This is a local R0 proof-of-concept, NOT a verified ModelScope deployment.
"""
from __future__ import annotations

import os
from app.runtime import build_task, run_case


def predict(equipment, material, medium, condition, evidence, question, mode):
    try:
        task = build_task(equipment, material, medium, condition, evidence, question)
        result = run_case(task, mode=mode)
        trace = result["trace"]
        answer = (trace.get("final_answer") or {}).get("conclusion") or "尚无结论"
        source_ids = (trace.get("final_answer") or {}).get("basis") or []
        references = []
        seen = set()
        for step in trace.get("steps", []):
            for source in (step.get("result") or {}).get("source") or []:
                cid = source.get("clause_id")
                if cid in source_ids and cid not in seen:
                    seen.add(cid)
                    references.append({
                        "clause_id": cid,
                        "standard_code": source.get("standard_code"),
                        "clause_no": source.get("clause_no"),
                        "page": source.get("page"),
                    })
        trace_for_ui = []
        for step in trace.get("steps", []):
            trace_for_ui.append({
                "step": step.get("step"),
                "tool": step.get("tool"),
                "args": step.get("args"),
                "result": step.get("result"),
                "observation": step.get("observation"),
                "blocked": step.get("blocked"),
                "block_kind": step.get("block_kind"),
                "elapsed_ms": step.get("elapsed_ms"),
            })
        meta = {
            "mode": result["mode"],
            "latency_ms": result["duration_ms"],
            "tool_calls": len(trace_for_ui),
            "evidence_checked": not result["basis_issues"],
            "evidence_issues": result["basis_issues"],
            "llm_parse": result["parse_stats"],
            "caveat": "引用存在性 != 引用内容真实性；本结果仅供辅助研判，不替代专业设备检验",
        }
        return answer, trace_for_ui, references, meta
    except Exception as exc:
        return f"本次执行未完成：{type(exc).__name__}: {exc}", [], [], {"status": "error"}


def build_demo():
    import gradio as gr

    with gr.Blocks(title="Haeness2 · 机械风险研判") as demo:
        gr.Markdown(
            "# Haeness2 · 机械设备风险研判\n"
            "验证标准知识库、三工具调用与审慎拒答的 Harness 演示。"
            "**缺少现场因子时不会凭空填写 RBI 等级。**"
        )
        with gr.Row():
            with gr.Column(scale=4):
                equipment = gr.Textbox(label="设备 / 部位", value="常压塔顶空冷器")
                material = gr.Textbox(label="材质", value="碳钢")
                medium = gr.Textbox(label="介质（逗号分隔）", value="湿硫化氢,氯化氢")
                condition = gr.Textbox(label="工况描述", value="操作温度110℃，压力0.1MPa，已投用8年")
                evidence = gr.Textbox(label="现场证据", lines=3, value="塔顶水pH 5.8，氯离子42mg/L，铁离子4.1mg/L")
                question = gr.Textbox(label="研判问题", lines=2, value="主要损伤机理是什么？还需要补充哪些信息？")
                mode = gr.Radio(
                    choices=[("规则基线（无需 API）", "rule"), ("真实 LLM（需环境变量）", "llm")],
                    value="rule", label="执行引擎",
                )
                go = gr.Button("开始研判", variant="primary")
            with gr.Column(scale=6):
                answer = gr.Textbox(label="最终结论", lines=7, interactive=False)
                meta = gr.JSON(label="运行诊断与质量检查")
        with gr.Tab("工具执行轨迹"):
            trace = gr.JSON(label="逐轮工具、参数、返回和执行耗时")
        with gr.Tab("标准证据"):
            references = gr.JSON(label="本次结论实际引用的条款出处")
        go.click(
            predict,
            inputs=[equipment, material, medium, condition, evidence, question, mode],
            outputs=[answer, trace, references, meta],
        )
    return demo


if __name__ == "__main__":
    build_demo().queue(default_concurrency_limit=2).launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.getenv("PORT", "7860")),
        share=False,
    )

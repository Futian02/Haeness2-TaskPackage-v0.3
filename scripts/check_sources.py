"""Read-only audit: verify which official source assets sparse checkout has fetched.

Run: python -B -m scripts.check_sources
Does not download, mutate, or verify the semantic accuracy of PDF contents.
"""
from __future__ import annotations

from pathlib import Path

from app.runtime import UPSTREAM


REQUIRED = [
    "任务包问题答复.docx",
    "资料获取与摘录表填写指南.md",
    "README.md",
    "01_RBI标准/条款摘录表_RBI.xlsx",
    "01_RBI标准/GBT26610.1-2022_基本要求和实施程序.pdf",
    "01_RBI标准/GBT26610.2-2022_基于风险的检验策略.pdf",
    "01_RBI标准/GBT26610.3-2014_风险的定性分析方法.pdf",
    "01_RBI标准/GBT26610.4-2022_失效可能性定量分析方法.pdf",
    "01_RBI标准/GBT26610.5-2022_失效后果定量分析方法.pdf",
    "01_RBI标准/补充规范/TSG21-2016_固定式压力容器安全技术监察规程.pdf",
    "02_损伤机理参考/条款摘录表_损伤机理.xlsx",
    "02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf",
    "03_案例样例/标注示范.md",
    "04_接口文档/工具接口规范.md",
    "04_接口文档/技术指标验证方法.md",
    "04_接口文档/enums.json",
    "04_接口文档/risk_level_mapping.xlsx",
    "05_提交区/clauses.jsonl",
    "05_提交区/trajectories.jsonl",
]


def check_sources() -> tuple[int, int]:
    missing = []
    for relative in REQUIRED:
        candidate = UPSTREAM / relative
        found = candidate.is_file()
        size = candidate.stat().st_size if found else 0
        print(f"{'PRESENT' if found else 'MISSING':7} {size:>10} bytes {relative}")
        if not found:
            missing.append(relative)
    print(f"summary: present={len(REQUIRED)-len(missing)}, missing={len(missing)}, required={len(REQUIRED)}")
    if missing:
        print("Incomplete sparse checkout; to download originals run:")
        print("  git -C upstream sparse-checkout add 01_RBI标准 02_损伤机理参考 03_案例样例")
    return len(REQUIRED) - len(missing), len(missing)


if __name__ == "__main__":
    _, missing = check_sources()
    raise SystemExit(1 if missing else 0)

"""校验两份 harness.py 内容一致（防止交付副本与骨架实现漂移）。

背景：官方护栏脚本 `04_接口文档/harness_skeleton/run_guardrail_tests.py` 只从
骨架目录 `import harness`；而 README 要求 `05_提交区/` 下也有可运行的 Harness 源码。
两处必须是同一份实现，否则"测的"和"交的"会不一致。

运行：.venv/Scripts/python.exe 05_提交区/_check_harness_sync.py
退出码：0 一致；1 不一致（需重新同步）。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPY = ROOT / "05_提交区" / "harness.py"
CANON = ROOT / "04_接口文档" / "harness_skeleton" / "harness.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for path in (COPY, CANON):
        if not path.exists():
            print(f"[FAIL] 缺少文件：{path}")
            return 1
    left, right = digest(COPY), digest(CANON)
    if left == right:
        print(f"[ OK ] 两份 harness.py 一致：{left[:16]}…")
        print(f"       交付副本 {COPY.relative_to(ROOT)}")
        print(f"       骨架实现 {CANON.relative_to(ROOT)}")
        return 0
    print("[FAIL] 两份 harness.py 内容不一致，需要同步：")
    print(f"       交付副本 {left[:16]}…  {COPY.relative_to(ROOT)}")
    print(f"       骨架实现 {right[:16]}…  {CANON.relative_to(ROOT)}")
    print("       同步命令：cp 05_提交区/harness.py 04_接口文档/harness_skeleton/harness.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())

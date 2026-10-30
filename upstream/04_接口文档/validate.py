#!/usr/bin/env python3
"""按 schema/ 中的三个 draft-07 Schema 校验提交数据（v0.3，不会改写输入文件）。

依赖：python -m pip install "jsonschema>=4.18,<5"

在任务包根目录运行示例：
  python 04_接口文档/validate.py                  # 每周五自查：查格式和引用，数量只报进度
  python 04_接口文档/validate.py --final          # 第10周终验：数量不达标也判失败
  python 04_接口文档/validate.py --clauses 05_提交区/clauses.jsonl
  python 04_接口文档/validate.py --clauses clauses.jsonl --trajectories trajectories.jsonl
  python 04_接口文档/validate.py --tool-responses response.json

无数据参数时检查 05_提交区/clauses.jsonl 和 trajectories.jsonl（trajectories.jsonl 不存在时只查条款）。
仅指定 --trajectories 时，同时读取该文件同目录的 clauses.jsonl 校验依据。
支持 JSONL（一行一条，忽略空白行）及 JSON（单个记录对象）。

逐条检查（两种模式都判定）：Schema 结构、字段、类型、枚举；主键唯一；basis 引用的 clause_id 必须在条款库；
  task_type 只能是 single_step / multi_step，且与调用次数一致（≥3 次为 multi_step，否则 single_step）。
数量检查（自查模式只打印进度，--final 模式不达标即失败）：
  条款 ≥300 条，且损伤机理与 RBI 两类都有；轨迹 ≥200 条；multi_step ≥40 条；三类特殊轨迹各 ≥15 条。
  只有逐条检查通过的记录才计数。

脚本不查：原文是否抄对、工具返回是否真实、特殊类型标注是否准确、样本是否同一模板换参数。
Schema 中的枚举是 enums.json 的快照，枚举表更新后需要同步 Schema。

退出码：0 通过；1 有记录不合规（--final 下还包括数量不达标）；2 依赖、Schema、文件读取或非轨迹空文件问题。
自查阶段看到退出码 1，先看输出里是「记录失败」还是「数量不足」：自查模式下数量不足不会导致退出码 1。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

try:
    from jsonschema import Draft7Validator
    from jsonschema.exceptions import SchemaError
    from referencing import Registry, Resource
    from referencing.exceptions import Unresolvable
except ImportError:
    print('缺少校验依赖，请运行：python -m pip install "jsonschema>=4.18,<5"', file=sys.stderr)
    raise SystemExit(2)


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILES = {
    "clause": "clause.schema.json",
    "trajectory": "trajectory.schema.json",
    "tool_response": "tool_response.schema.json",
}
SPECIAL_TYPE_MIN_COUNT = 15  # 规格说明 3.3：三类特殊轨迹各至少 15 条。
CLAUSE_MIN_COUNT = 300       # 验收清单：条款 ≥300 条
TRAJECTORY_MIN_COUNT = 200   # 验收清单：轨迹 ≥200 条
MULTI_STEP_MIN_COUNT = 40    # 验收清单：multi_step ≥40 条
KNOWLEDGE_TYPES = ("damage_mechanism", "rbi")
TASK_TYPES = ("single_step", "multi_step")


def reject_constant(value: str) -> None:
    raise ValueError(f"JSON 不允许非有限数值 {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """防止重复 JSON 键被解析器静默覆盖。"""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 对象出现重复键 {key!r}")
        result[key] = value
    return result


def parse_json(text: str) -> Any:
    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)


def load_validators(schema_dir: Path) -> dict[str, Draft7Validator]:
    """每次启动加载三个 Schema；为相对 $ref 注册本地资源，无需联网。"""
    schemas = {}
    resources = []
    for kind, filename in SCHEMA_FILES.items():
        path = (schema_dir / filename).resolve()
        schema = parse_json(path.read_text(encoding="utf-8-sig"))
        if not isinstance(schema, dict) or schema.get("$schema") != Draft7Validator.META_SCHEMA["$id"]:
            raise ValueError(f"{path} 必须声明 draft-07")
        Draft7Validator.check_schema(schema)
        # 文件 URI 只用于本次加载的引用基址，不写回 Schema 文件。
        schema["$id"] = path.as_uri()
        schemas[kind] = schema
        resources.append((path.as_uri(), Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    return {kind: Draft7Validator(schema, registry=registry) for kind, schema in schemas.items()}


def pointer(parts: Any) -> str:
    """把 Schema 报错路径转换成 JSON Pointer，数组下标从 0 开始。"""
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


@dataclass
class Record:
    path: Path
    line: int
    data: Any
    valid: bool = True

    def fail(self, location: str, message: str) -> None:
        self.valid = False
        print(f"{self.path}:{self.line} {location}: {message}", file=sys.stderr)


def validate_file(path: Path, validator: Draft7Validator, *, allow_empty: bool = False) -> list[Record]:
    records = []
    with path.open(encoding="utf-8-sig") as stream:
        entries = [(1, stream.read())] if path.suffix.lower() == ".json" else enumerate(stream, 1)
        for line, text in entries:
            if not text.strip():
                continue
            record = Record(path, line, None)
            records.append(record)
            try:
                record.data = parse_json(text)
            except (ValueError, RecursionError) as error:
                record.fail("/", f"JSON 解析失败：{error}")
                continue
            for error in validator.iter_errors(record.data):
                record.fail(pointer(error.absolute_path), error.message)
    if not records and not allow_empty:
        raise ValueError(f"{path} 没有可校验的记录")
    return records


def unique_ids(records: list[Record], key: str) -> set[str]:
    """单条 JSON Schema 无法比较 JSONL 中不同记录的主键。"""
    seen: dict[str, Record] = {}
    for record in records:
        if not record.valid:
            continue
        value = record.data[key]
        if value in seen:
            first = seen[value]
            record.fail(f"/{key}", f"主键 {value!r} 重复，首次出现于 {first.path}:{first.line}")
        else:
            seen[value] = record
    return set(seen)


def check_basis(records: list[Record], clause_ids: set[str]) -> None:
    """按规格说明 3.2，将结论依据与已通过结构校验的条款主键比对。"""
    for record in records:
        if not record.valid:
            continue
        for index, clause_id in enumerate(record.data["final_answer"]["basis"]):
            if clause_id not in clause_ids:
                record.fail(f"/final_answer/basis/{index}", f"条款 {clause_id!r} 不在通过校验的条款库中")


def check_task_type(records: list[Record]) -> None:
    """task_type 与调用次数一致：≥3 次为 multi_step，否则为 single_step。"""
    for record in records:
        if not record.valid:
            continue
        task_type, n = record.data.get("task_type"), len(record.data.get("steps", []))
        if task_type not in TASK_TYPES:
            record.fail("/task_type", f"只能是 {list(TASK_TYPES)}，收到 {task_type!r}")
        elif (n >= 3) != (task_type == "multi_step"):
            expected = "multi_step" if n >= 3 else "single_step"
            record.fail("/task_type", f"共 {n} 次调用，task_type 应为 {expected!r}")


def quota_line(label: str, count: int, required: int, final: bool) -> bool:
    missing = max(0, required - count)
    text = f"{label}：有效 {count} 条，要求至少 {required} 条"
    if not missing:
        print(f"{text}，已达标。")
        return True
    if final:
        print(f"[数量不足] {text}，还缺 {missing} 条。", file=sys.stderr)
    else:
        print(f"[进度] {text}，还差 {missing} 条（自查模式不计为失败）。")
    return False


def check_clause_quotas(records: list[Record], final: bool) -> bool:
    valid = [r for r in records if r.valid]
    ok = quota_line("条款总数", len(valid), CLAUSE_MIN_COUNT, final)
    for kt in KNOWLEDGE_TYPES:
        n = sum(r.data["knowledge_type"] == kt for r in valid)
        ok &= quota_line(f"条款 knowledge_type={kt}", n, 1, final)
    return ok


def check_trajectory_quotas(records: list[Record], special_types: list[str], final: bool) -> bool:
    valid = [r for r in records if r.valid]
    ok = quota_line("轨迹总数", len(valid), TRAJECTORY_MIN_COUNT, final)
    ok &= quota_line("multi_step 轨迹", sum(r.data["task_type"] == "multi_step" for r in valid), MULTI_STEP_MIN_COUNT, final)
    for special_type in special_types:
        n = sum(r.data.get("special_type") == special_type for r in valid)
        ok &= quota_line(f"特殊轨迹 {special_type}", n, SPECIAL_TYPE_MIN_COUNT, final)
    return ok


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验条款、轨迹及工具返回：Schema、主键、basis 引用、task_type；并统计数量配额。",
        epilog="默认自查模式只报告数量进度；加 --final 时数量不达标也判失败。原文及返回真实性仍需人工核对。",
    )
    parser.add_argument("--final", action="store_true", help="终验模式：条款、轨迹、多步、特殊轨迹数量不达标即失败")
    parser.add_argument("--clauses", type=Path, help="条款 JSONL 或单条 JSON 文件")
    parser.add_argument("--trajectories", type=Path, help="轨迹 JSONL 或单条 JSON 文件")
    parser.add_argument("--tool-responses", type=Path, help="独立工具返回 JSONL 或单条 JSON 文件")
    parser.add_argument("--schema-dir", type=Path, default=BASE_DIR / "schema", help="Schema 目录，默认使用本脚本旁的 schema/")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not any((args.clauses, args.trajectories, args.tool_responses)):
        submission_dir = BASE_DIR.parent / "05_提交区"
        args.clauses = submission_dir / "clauses.jsonl"
        args.trajectories = submission_dir / "trajectories.jsonl"
        if not args.trajectories.exists() and not args.final:
            print(f"未找到 {args.trajectories}，本次只校验条款。")
            args.trajectories = None
    elif args.trajectories and not args.clauses:
        args.clauses = args.trajectories.parent / "clauses.jsonl"

    paths = {"clause": args.clauses, "trajectory": args.trajectories, "tool_response": args.tool_responses}
    try:
        validators = load_validators(args.schema_dir)
        records = {
            kind: validate_file(path.resolve(), validators[kind], allow_empty=(kind == "trajectory"))
            for kind, path in paths.items() if path is not None
        }
        clause_ids = unique_ids(records.get("clause", []), "clause_id")
        unique_ids(records.get("trajectory", []), "traj_id")
        check_basis(records.get("trajectory", []), clause_ids)
        check_task_type(records.get("trajectory", []))
    except (OSError, UnicodeError, ValueError, SchemaError, Unresolvable, RecursionError) as error:
        print(f"无法完成校验：{error}", file=sys.stderr)
        return 2

    failed = False
    quotas_ok = True
    if "clause" in records:
        quotas_ok &= check_clause_quotas(records["clause"], args.final)
    if "trajectory" in records:
        special_types = validators["trajectory"].schema["properties"]["special_type"]["enum"]
        quotas_ok &= check_trajectory_quotas(records["trajectory"], special_types, args.final)
    if args.final and not quotas_ok:
        failed = True
    for kind, rows in records.items():
        invalid = sum(not row.valid for row in rows)
        failed |= invalid > 0
        valid = len(rows) - invalid
        rate = f"通过率 {valid / len(rows):.1%}" if rows else "无记录"
        print(f"{paths[kind].resolve()}：{len(rows)} 条，{valid} 条通过，{invalid} 条记录失败，{rate}")
    mode = "终验模式" if args.final else "自查模式"
    print(f"[{mode}] 结论：{'不通过' if failed else '通过'}")
    return 1 if failed else 0


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")
    raise SystemExit(main())

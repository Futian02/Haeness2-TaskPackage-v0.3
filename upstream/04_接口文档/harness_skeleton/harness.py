"""
Harness —— 面向设备风险研判的工具调用框架（实现版）

由官方骨架 04_接口文档/harness_skeleton/harness.py 改造而来。
类名、字段名、四类护栏规则、轨迹字段与骨架完全一致，只填了骨架标注的 TODO：

  TODO-1  build_registry()   : mock 函数 -> 真实查 clauses.jsonl 的三个工具（tools.py）
  TODO-2  Harness.run 的 planner  : 规则决策器 + 可选大模型决策器（LLMPlanner）
  TODO-3  Harness._summarize      : 按各工具 result 结构生成观察
  TODO-4  轨迹留痕               : to_record 导出 + run_batch 批量落盘 + 完整率统计

四个模块：工具注册 / 执行循环 / 安全护栏 / 轨迹留痕。

运行：
  python 05_提交区/harness.py            # 不需要大模型，用规则决策器跑演示
  HARNESS_LLM=1 python 05_提交区/harness.py   # 配置好接口后用大模型决策器

注意：写文件一律用 save_jsonl()。Windows 下用 > 重定向会存成 GBK，validate.py 读不了。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent


def _find_submit_dir() -> Path:
    """定位 05_提交区。

    本实现会同时放在 `05_提交区/`（交付源码）和 `04_接口文档/harness_skeleton/`
    （官方 run_guardrail_tests.py 从这里 import），因此不能假设 __file__ 的父目录
    就是提交区——否则换个位置就找不到 tools.py / clauses.jsonl。
    """
    if (_HERE / "tools.py").exists():
        return _HERE
    for base in _HERE.parents:
        candidate = base / "05_提交区"
        if (candidate / "tools.py").exists():
            return candidate
    return _HERE


SUBMIT_DIR = _find_submit_dir()
PROJECT_ROOT = SUBMIT_DIR.parent

# 让 `import tools` 在任意工作目录下都成立
if str(SUBMIT_DIR) not in sys.path:
    sys.path.insert(0, str(SUBMIT_DIR))

import tools as tool_impl  # noqa: E402


# =============================================================
# 0. 统一返回外壳 —— 不可修改（委托给 tools，保持单一实现）
# =============================================================

def make_response(
    status: str = "ok",
    in_domain: bool = True,
    result: Optional[dict] = None,
    source: Optional[List[dict]] = None,
    message: str = "",
) -> dict:
    """所有工具必须通过这个函数构造返回值。逻辑与 tools.make_response 完全一致。"""
    return tool_impl.make_response(
        status=status, in_domain=in_domain, result=result, source=source, message=message
    )


def _data_path(filename: str) -> Path:
    """在若干候选位置中解析数据文件，兼容本文件放在 05_提交区 或 harness_skeleton 下。"""
    candidates = [
        SUBMIT_DIR / filename,
        PROJECT_ROOT / filename,
        PROJECT_ROOT / "04_接口文档" / filename,
        SUBMIT_DIR.parent / "04_接口文档" / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


# =============================================================
# 1. 工具注册
# =============================================================

@dataclass
class ToolSpec:
    name: str
    func: Callable[..., dict]
    description: str
    parameters: Dict[str, dict]      # 参数名 -> {"type":..., "required":bool, "enum":[...]}


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具重复注册: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def to_schema(self) -> List[dict]:
        """转成可以塞进大模型 prompt 的工具声明。"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            }
            for s in self._tools.values()
        ]


# =============================================================
# 2. 安全护栏 —— 四类异常
# =============================================================

@lru_cache(maxsize=1)
def load_enums() -> Dict[str, Dict[str, dict]]:
    """读取并缓存枚举表；路径相对于本文件，不依赖运行时的工作目录。"""
    enum_path = _data_path("enums.json")
    with enum_path.open(encoding="utf-8") as f:
        data = json.load(f)

    tables = {}
    for pname in ("material", "medium", "equipment_type"):
        table = data[pname]
        if not isinstance(table, dict) or not table:
            raise ValueError(f"枚举表 {pname!r} 必须是非空对象")
        owners = {}
        for canonical, entry in table.items():
            if not isinstance(canonical, str) or not canonical or not isinstance(entry, dict):
                raise ValueError(f"枚举表 {pname!r} 含非法条目")
            aliases = entry.get("aliases")
            if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
                raise ValueError(f"枚举项 {pname}.{canonical} 的 aliases 必须是字符串数组")
            for value in [canonical, *aliases]:
                if value in owners and owners[value] != canonical:
                    raise ValueError(f"枚举表 {pname!r} 中的写法 {value!r} 对应多个标准值")
                owners[value] = canonical
        tables[pname] = table
    return tables


# 启动时加载一次；后续校验和再次调用 load_enums() 都复用缓存。
ENUM_TABLES = load_enums()


_JSON_TYPES = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "boolean": lambda v: isinstance(v, bool),
}


def _type_ok(value: Any, expected: str) -> bool:
    check = _JSON_TYPES.get(expected)
    return check(value) if check else True


@lru_cache(maxsize=1)
def load_material_family() -> Dict[str, List[str]]:
    """牌号 -> 所属材料类别,见 material_family.json。"""
    path = _data_path("material_family.json")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v["belongs_to"] for k, v in data["family"].items()}


def material_candidates(material: str) -> List[str]:
    """条款匹配用:返回入参材质本身及其所属的全部类别。
    例:06Cr19Ni10 -> [06Cr19Ni10, 300系列不锈钢, 奥氏体不锈钢, 不锈钢]
    只向上扩展(牌号 -> 类别),不向下扩展(类别 -> 牌号)。"""
    family = load_material_family()
    out, queue = [], [material]
    while queue:
        m = queue.pop(0)
        if m not in out:
            out.append(m)
            queue.extend(family.get(m, []))
    return out


class GuardrailError(Exception):
    def __init__(self, kind: str, detail: str):
        self.kind = kind          # unknown_tool | missing_param | out_of_domain | bad_format
        self.detail = detail
        super().__init__(f"[{kind}] {detail}")


class Guardrail:
    """四类异常各需构造 >=3 个测试用例,拦截率必须 100%,且不得误拦正常调用。"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    # --- 第一类:工具名错误 ---
    def check_tool_exists(self, tool_name: str) -> ToolSpec:
        spec = self.registry.get(tool_name)
        if spec is None:
            raise GuardrailError(
                "unknown_tool",
                f"工具 {tool_name!r} 未注册。可用工具: {self.registry.names()}",
            )
        return spec

    # --- 第二类:参数缺失 / 参数非法 ---
    def check_params(self, spec: ToolSpec, args: dict) -> None:
        if not isinstance(args, dict):
            raise GuardrailError("bad_format", f"args 必须是 dict,收到 {type(args).__name__}")

        for pname, pconf in spec.parameters.items():
            if pconf.get("required") and pname not in args:
                raise GuardrailError("missing_param", f"缺少必填参数 {pname!r}")

        normalized_args = {}
        for pname, pvalue in args.items():
            pconf = spec.parameters.get(pname)
            if pconf is None:
                raise GuardrailError("bad_format", f"未知参数 {pname!r}")
            expected = pconf.get("type")
            if expected and not _type_ok(pvalue, expected):
                raise GuardrailError(
                    "bad_format", f"参数 {pname!r} 应为 {expected},收到 {type(pvalue).__name__}: {pvalue!r}"
                )
            if "maximum" in pconf and _type_ok(pvalue, "number") and pvalue > pconf["maximum"]:
                raise GuardrailError("bad_format", f"参数 {pname!r} 超过上限 {pconf['maximum']}")
            table = ENUM_TABLES.get(pname)
            enum = pconf.get("enum")
            if table is not None:
                # 文件提供白名单；参数自身若声明更窄的 enum，仍保留该限制。
                enum = [value for value in table if not enum or value in enum]
            if table is not None or enum:
                values = pvalue if isinstance(pvalue, list) else [pvalue]
                normalized_values = []
                for v in values:
                    canonical = v
                    if table is not None and isinstance(v, str) and v not in table:
                        canonical = next(
                            (name for name, entry in table.items() if v in entry["aliases"]),
                            v,
                        )
                    if canonical not in enum:
                        suggestions = get_close_matches(
                            str(v), [str(value) for value in enum], n=3, cutoff=0.0
                        )
                        raise GuardrailError(
                            "bad_format",
                            f"参数 {pname!r} 的值 {v!r} 不在枚举表中。"
                            f"最接近的 {len(suggestions)} 个合法取值: {suggestions!r}",
                        )
                    normalized_values.append(canonical)
                normalized_args[pname] = (
                    normalized_values if isinstance(pvalue, list) else normalized_values[0]
                )

        # 全部校验通过后再写回，工具执行与轨迹记录都会使用标准值。
        args.update(normalized_args)

    # --- 第三类:超出适用范围 ---
    def check_in_domain(self, resp: dict) -> None:
        """注意:超范围不是报错,是正常返回 in_domain=False。
        这里拦截的是"超范围却仍然给了结论"这种情况。"""
        if resp.get("in_domain") is False and resp.get("result"):
            raise GuardrailError(
                "out_of_domain",
                "in_domain=False 时 result 必须为空,不得给出结论",
            )

    # --- 第四类:输出格式不合规 ---
    def check_response_format(self, resp: Any) -> None:
        if not isinstance(resp, dict):
            raise GuardrailError("bad_format", f"返回必须是 dict,收到 {type(resp).__name__}")
        required = {"status", "in_domain", "result", "source", "message"}
        missing = required - set(resp.keys())
        if missing:
            raise GuardrailError("bad_format", f"返回缺少字段: {sorted(missing)}")
        if resp["status"] not in {"ok", "out_of_domain", "not_found", "error"}:
            raise GuardrailError("bad_format", f"非法 status: {resp['status']!r}")
        if resp["status"] == "ok" and not resp["source"]:
            raise GuardrailError("bad_format", "status=ok 但 source 为空")


# =============================================================
# 3. 轨迹留痕 —— 完整率必须 100%,失败和被拦截的调用也要记
# =============================================================

@dataclass
class Step:
    step: int
    thought: str
    tool: str
    args: dict
    result: dict = field(default_factory=dict)
    observation: str = ""
    blocked: bool = False            # 是否被护栏拦截
    block_kind: str = ""             # 拦截类型
    elapsed_ms: int = 0


class DatasetExportError(Exception):
    """轨迹不能写进 trajectories.jsonl 时抛出。"""


RECORD_STEP_FIELDS = ("step", "thought", "tool", "args", "result", "observation")


@dataclass
class Trajectory:
    traj_id: str
    task_type: str                   # single_step | multi_step,由调用次数决定
    input: dict
    steps: List[Step] = field(default_factory=list)
    final_answer: dict = field(default_factory=dict)
    annotator: str = ""
    checked: bool = False
    special_type: Optional[str] = None   # exclusion | insufficient_info | out_of_domain;普通轨迹保持 None
    # 审查扩展接口的产出,只进运行日志(to_dict),不进数据集记录(to_record)——
    # trajectory.schema.json 的 additionalProperties=false,数据集字段不可增减。
    review: Optional[dict] = None

    def _task_type(self) -> str:
        # 多步定义:调用次数 >= 3(同一工具多次调用也算)
        return "multi_step" if len(self.steps) >= 3 else "single_step"

    def to_dict(self) -> dict:
        """运行日志:保留全部步骤及拦截信息,用于统计轨迹完整率。"""
        d = asdict(self)
        d["task_type"] = self._task_type()
        return d

    def to_record(self) -> dict:
        """数据集记录:字段与 trajectory.schema.json 一致,可直接写入 trajectories.jsonl。"""
        blocked = [s.step for s in self.steps if s.blocked]
        if blocked:
            raise DatasetExportError(
                f"{self.traj_id} 第 {blocked} 步被护栏拦截或执行异常,这条只保留在运行日志里,不进数据集"
            )
        if not self.final_answer:
            raise DatasetExportError(f"{self.traj_id} 没有 final_answer")
        if self.review is not None and not self.review.get("passed", True):
            issues = "；".join(str(i) for i in (self.review.get("issues") or [])) or "未说明原因"
            raise DatasetExportError(
                f"{self.traj_id} 审查未通过,这条只保留在运行日志里,不进数据集:{issues}"
            )
        missing = [k for k in ("equipment", "material", "medium", "operating_condition", "field_evidence", "question")
                   if k not in self.input]
        if missing:
            raise DatasetExportError(f"{self.traj_id} 的 input 缺少 {missing};没有的信息填空字符串,不要省略字段")
        record = {"traj_id": self.traj_id, "task_type": self._task_type()}
        if self.special_type:
            record["special_type"] = self.special_type
        record["input"] = self.input
        record["steps"] = [{k: getattr(s, k) for k in RECORD_STEP_FIELDS} for s in self.steps]
        record["final_answer"] = self.final_answer
        record["annotator"] = self.annotator
        record["checked"] = self.checked
        return record

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def save_jsonl(path, records: Iterable[dict]) -> Path:
    """按 UTF-8 写 JSONL。所有输出文件都用这个函数写。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


# =============================================================
# 4. 执行循环
# =============================================================

class Harness:
    MAX_ROUNDS = 8                   # 指标要求支持 >=5 轮,这里留余量

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.guard = Guardrail(registry)

    def call_tool(self, tool_name: str, args: dict) -> dict:
        """单次工具调用,全程走护栏。"""
        spec = self.guard.check_tool_exists(tool_name)
        self.guard.check_params(spec, args)
        resp = spec.func(**args)
        self.guard.check_response_format(resp)
        self.guard.check_in_domain(resp)
        return resp

    def run(self, traj_id: str, task_input: dict, planner: Callable,
            special_type: Optional[str] = None, annotator: str = "",
            checked: bool = False, reviewer: Optional[Callable] = None) -> Trajectory:
        """
        planner: 决定下一步做什么的函数。
                 签名 planner(task_input, history) -> dict
                 返回 {"thought":..., "tool":..., "args":{...}}
                 或   {"thought":..., "final_answer":{...}}  表示结束
                 可在结束决策里附带 "special_type" 覆盖默认值。

        reviewer: 可选的**审查扩展接口**（README 5.1 要求「预留研判、审查、建议三类
                 智能体协作的扩展接口」）。签名 reviewer(record) -> dict，
                 record 是本条轨迹的 dict 形态，返回形如
                     {"passed": bool, "issues": [str, ...]}
                 不传则完全不生效，现有行为一字不变。
                 审查结果只记入运行日志（Trajectory.to_dict），**不写入
                 trajectories.jsonl** —— 数据集字段由 trajectory.schema.json 固定，
                 additionalProperties=false，不允许新增字段。
                 审查不通过时，轨迹标记为不通过并把问题写进 observation，
                 该轨迹不导出到数据集（与被护栏拦截的处理一致）。
        """
        traj = Trajectory(traj_id=traj_id, task_type="single_step", input=task_input,
                          special_type=special_type, annotator=annotator, checked=checked)
        history: List[Step] = []

        for i in range(1, self.MAX_ROUNDS + 1):
            decision = planner(task_input, history)

            if "final_answer" in decision:
                traj.final_answer = decision["final_answer"]
                if decision.get("special_type"):
                    traj.special_type = decision["special_type"]
                break

            step = Step(
                step=i,
                thought=decision.get("thought", ""),
                tool=decision.get("tool", ""),
                args=decision.get("args", {}),
            )
            t0 = time.time()
            try:
                resp = self.call_tool(step.tool, step.args)
                step.result = resp
                step.observation = self._summarize(resp)
                # 工具主动返回 error 属"执行异常"（README 第四部分：执行异常只记运行日志，
                # 不写进 trajectories.jsonl）。按拦截处理，由 to_record() 挡在数据集外。
                if resp.get("status") == "error":
                    step.blocked = True
                    step.block_kind = "tool_error"
            except GuardrailError as e:
                # 被拦截也要完整记录 —— 轨迹完整率 100%
                step.blocked = True
                step.block_kind = e.kind
                step.observation = f"调用被护栏拦截: {e.detail}"
            except Exception as e:
                step.blocked = True
                step.block_kind = "error"
                step.observation = f"工具执行异常: {e}"
            step.elapsed_ms = int((time.time() - t0) * 1000)

            traj.steps.append(step)
            history.append(step)
        else:
            traj.final_answer = {
                "conclusion": f"达到最大轮次 {self.MAX_ROUNDS},未能得出结论",
                "basis": sorted({s for step in traj.steps for s in _basis_of(step.result)}),
            }

        # ---- 审查扩展接口（可选，不传则完全不生效）----
        if reviewer is not None:
            traj.review = self._apply_reviewer(reviewer, traj)

        return traj

    @staticmethod
    def _apply_reviewer(reviewer: Callable, traj: Trajectory) -> dict:
        """调用审查回调并把结果落到轨迹上。

        约定：reviewer(record) -> {"passed": bool, "issues": [...]}
        - passed=False 时，轨迹被标记为不通过，且最后一步的 observation 追加问题说明；
          该轨迹随后会被 to_record() 挡在数据集之外（与被护栏拦截的处理一致）。
        - 审查回调自身抛异常时，按"执行异常"处理，不影响轨迹其余部分。
        """
        try:
            verdict = reviewer(traj.to_dict())
        except Exception as exc:  # 审查体自身出错不影响主流程
            return {"passed": False, "issues": [f"审查回调执行异常: {exc}"], "error": True}

        if not isinstance(verdict, dict):
            return {"passed": False, "issues": ["审查回调未返回 dict"], "error": True}

        passed = bool(verdict.get("passed", True))
        issues = verdict.get("issues") or []
        if not isinstance(issues, list):
            issues = [str(issues)]
        review = {"passed": passed, "issues": [str(i) for i in issues]}
        if not passed:
            note = "审查未通过：" + "；".join(review["issues"]) if review["issues"] else "审查未通过"
            if traj.steps:
                traj.steps[-1].observation = (traj.steps[-1].observation + " | " + note).strip()
            else:
                traj.final_answer = dict(traj.final_answer or {})
                traj.final_answer["conclusion"] = (
                    str(traj.final_answer.get("conclusion", "")) + " | " + note).strip()
        return review

    # ---------------- TODO-3：按各工具 result 结构生成观察 ----------------
    @staticmethod
    def _summarize(resp: dict) -> str:
        """把工具返回压成一句话,喂给下一轮决策。"""
        status = resp.get("status")
        if status != "ok":
            return f"{status}: {resp.get('message', '')}"
        if not resp.get("in_domain", True):
            return f"超出适用范围: {resp.get('message', '')}"

        result = resp.get("result") or {}
        if "mechanisms" in result:
            mechs = result.get("mechanisms") or []
            names = "、".join(m.get("name", "") for m in mechs) or "无"
            text = f"候选 {len(mechs)} 个: {names}。"
            if result.get("excluded"):
                text += f"已排除 {len(result['excluded'])} 个。"
            if result.get("discriminator"):
                text += f"鉴别要点: {result['discriminator']}"
            return text
        if "hits" in result:
            hits = result.get("hits") or []
            if not hits:
                return "未命中任何条款。"
            first = hits[0]
            return f"命中 {len(hits)} 条;首条 {first.get('clause_id', '')}《{first.get('title', '')}》(score {first.get('score')})。"
        if "risk_level_unified" in result or "likelihood" in result:
            level = result.get("risk_level") or "未给出"
            unified = result.get("risk_level_unified") or "未给出"
            interval = result.get("inspection_interval_year")
            interval_text = f"{interval} 年" if interval is not None else "无条款依据(null)"
            methods = "、".join(result.get("inspection_methods") or []) or "无"
            return f"等级 {level}({unified}),检验周期 {interval_text},推荐方法 {methods}。"
        return f"命中 {len(resp.get('source') or [])} 条依据。"


def _basis_of(resp: dict) -> List[str]:
    """从一次工具返回里取出可作为结论依据的 clause_id。"""
    out: List[str] = []
    for item in (resp or {}).get("source") or []:
        cid = item.get("clause_id")
        if cid and cid not in out:
            out.append(cid)
    return out


# =============================================================
# 5. 决策器
# =============================================================

# ---------------------------------------------------------------- 输入解析
_TEMP_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:℃|°C)")
_PRESSURE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*MPa", re.IGNORECASE)
_YEARS_RE = re.compile(r"(?:投用|服役|已用)\s*(\d+(?:\.\d+)?)\s*年")
_PH_RE = re.compile(r"pH\s*[:：=为]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_CL_RE = re.compile(r"氯离子[^\d]{0,12}(\d+(?:\.\d+)?)")
_FE_RE = re.compile(r"铁离子[^\d]{0,24}?(\d+(?:\.\d+)?)(?![\d.]*\d)")

_EQUIPMENT_RULES: List[Tuple[str, str]] = [
    ("加热炉", "加热炉"), ("炉", "加热炉"),
    ("空冷器", "换热器"), ("换热器", "换热器"), ("冷凝器", "换热器"), ("冷却器", "换热器"),
    ("储罐", "储罐"), ("贮罐", "储罐"),
    ("管道", "管道"), ("管线", "管道"),
    ("塔", "塔"),
    ("容器", "容器"), ("罐", "容器"), ("分离器", "容器"),
]


def parse_input(task_input: dict) -> dict:
    """从原始输入里抽取结构化参数。抽不到的项保持 None，绝不臆造。"""
    blob = " ".join(str(task_input.get(k) or "") for k in
                    ("equipment", "operating_condition", "field_evidence", "question"))
    parsed: Dict[str, Any] = {
        "temperature_c": None,
        "pressure_mpa": None,
        "service_years": None,
        "equipment_type": None,
        "evidence": {},
    }
    m = _TEMP_RE.search(blob)
    if m:
        parsed["temperature_c"] = float(m.group(1))
    m = _PRESSURE_RE.search(blob)
    if m:
        parsed["pressure_mpa"] = float(m.group(1))
    m = _YEARS_RE.search(blob)
    if m:
        parsed["service_years"] = float(m.group(1))

    equipment_text = str(task_input.get("equipment") or "")
    for keyword, etype in _EQUIPMENT_RULES:
        if keyword in equipment_text:
            parsed["equipment_type"] = etype
            break

    evidence: Dict[str, Any] = {}
    m = _PH_RE.search(blob)
    if m:
        evidence["ph"] = float(m.group(1))
    m = _CL_RE.search(blob)
    if m:
        evidence["cl_ppm"] = float(m.group(1))
    m = _FE_RE.search(blob)
    if m:
        evidence["fe_ppm"] = float(m.group(1))
    if re.search(r"(未见|未发现|没有)[^。；;]{0,6}减薄|壁厚[^。；;]{0,8}(正常|无明显)", blob):
        evidence["wall_thinning"] = False
    elif re.search(r"减薄|壁厚[^。；;]{0,6}(减薄|下降)", blob):
        evidence["wall_thinning"] = True
    if re.search(r"(未见|未发现|没有)[^。；;]{0,6}裂纹", blob):
        evidence["crack_found"] = False
    elif "裂纹" in blob:
        evidence["crack_found"] = True
    parsed["evidence"] = evidence
    return parsed


# ---------------------------------------------------------------- 判据匹配
# 判据来源：damage_mechanism_query 返回的八段式（detection_methods / influencing_factors /
# description），即条款原文内容；证据来源：用户输入的自由文本。
# 这里不引入"某现象对应某机理"的领域词表，只做两件通用的事：
#   1) 抽取条款里明确写出的"监测项"，看现场数据是否涉及；
#   2) 抽取条款里明确写出的数值判据（如 pH 低于 4.5），用实测值校验是否满足。

def _lcs_len(a: str, b: str) -> int:
    """最长公共子串长度（字符串都很短，直接 DP）。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


_NEGATION_WORDS = ("未见", "未发现", "未检出", "未出现", "没有", "无异常", "正常", "无腐蚀")


def _positive_mention(item: str, evidence: str) -> bool:
    """判断现场证据是否**肯定地**提到某个监测项。

    只用 LCS 会把"裂纹活动"匹配到「未发现裂纹」这种否定证据上，
    因此还要检查命中位置前后 10 字内是否出现否定词。
    """
    n = len(item)
    for length in range(min(n, 8), 1, -1):
        for start in range(n - length + 1):
            piece = item[start : start + length]
            pos = evidence.find(piece)
            if pos < 0:
                continue
            context = evidence[max(0, pos - 10) : pos + length + 10]
            if any(word in context for word in _NEGATION_WORDS):
                continue
            return True
    return False


def _monitor_items(mechanism: dict) -> List[str]:
    """从条款里抽"监测项"：形如「监测换热器压降和换热效率」-> 换热器压降 / 换热效率。"""
    texts = list(mechanism.get("detection_methods") or []) + list(mechanism.get("influencing_factors") or [])
    items: List[str] = []
    for text in texts:
        for match in re.finditer(r"监测([^。；;]{2,26})", str(text)):
            for part in re.split(r"[、，,]|以及|[和与]", match.group(1)):
                part = part.strip(" 。.：:（）()")
                if 2 <= len(part) <= 14 and part not in items:
                    items.append(part)
    return items


def _ph_criteria(mechanism: dict) -> List[Tuple[str, float]]:
    """从条款里抽 pH 数值判据，如「pH值低于4.5时腐蚀性强」。"""
    texts = [mechanism.get("description", "")] + list(mechanism.get("influencing_factors") or [])
    found: List[Tuple[str, float]] = []
    for text in texts:
        for match in re.finditer(r"pH[^。；;]{0,14}?(低于|小于|高于|大于)\s*(\d+(?:\.\d+)?)", str(text)):
            found.append((match.group(1), float(match.group(2))))
    return found


# 运算符归一化：条款里常见"不超过/不低于"，不能把"不超过400℃"当成"超过400℃"
_OP_NORMALIZE = {"低于": "<", "小于": "<", "高于": ">", "大于": ">", "超过": ">",
                 "不超过": "<=", "不高于": "<=", "不大于": "<=",
                 "不低于": ">=", "不小于": ">="}
_OP_PATTERN = "不超过|不高于|不大于|不低于|不小于|低于|小于|高于|大于|超过"

# 温度判据要求"阈值后面紧跟发生类措辞"，否则不采用。
# 原因：条款里有大量反向或非门槛表述，例如
#   氨应力腐蚀开裂「低于-5℃时几乎不会发生」、氢脆「高于82℃时通常不会发生」、
#   石墨化「低于427℃时速率极慢」、连多硫酸「…不会敏化」。
# 朴素解析会把方向搞反，宁可少用，不可用错。
_TEMP_CUE = (r"(开始发生|才会发生|易发生|容易发生|常见|可能出现|可能发生|可能闪蒸"
             r"|析出|结垢|敏感|(?<!不会)(?<!不再)发生)")
_TEMP_CRIT_RE = re.compile(
    r"温度[^。；;]{0,8}?(" + _OP_PATTERN + r")\s*(-?\d+(?:\.\d+)?)\s*℃[^。；;]{0,12}?"
    + _TEMP_CUE)
_CONC_CRIT_RE = re.compile(
    r"(" + _OP_PATTERN + r")\s*(\d+(?:\.\d+)?)\s*(mg/L|mg/l|ppm)")
# 物质 -> evidence 字段，依据《工具接口规范》2.2 对子字段的定义（cl_ppm=氯离子含量等）
_SPECIES_FIELD = (("氯离子", "cl_ppm"), ("氯化物", "cl_ppm"),
                  ("硫化氢", "h2s_ppm"), ("H2S", "h2s_ppm"), ("铁离子", "fe_ppm"))


def _holds(operator: str, value: float, threshold: float) -> bool:
    """按归一化后的运算符判断实测值是否满足条款判据。"""
    symbol = _OP_NORMALIZE.get(operator, operator)
    if symbol == "<":
        return value < threshold
    if symbol == "<=":
        return value <= threshold
    if symbol == ">":
        return value > threshold
    return value >= threshold


def _temperature_criteria(mechanism: dict) -> List[Tuple[str, float]]:
    """抽温度判据。同一句里同时出现"高于"和"低于"的（如 475℃ 脆化的敏感区间），
    属双向区间而非单侧阈值，整句跳过。"""
    texts = [mechanism.get("description", "")] + list(mechanism.get("influencing_factors") or [])
    found: List[Tuple[str, float]] = []
    for text in texts:
        for sentence in re.split(r"(?<=[。；;])", str(text)):
            for operator, value, _cue in _TEMP_CRIT_RE.findall(sentence):
                item = (_OP_NORMALIZE.get(operator, ">"), float(value))
                if item not in found:
                    found.append(item)
    return found


def _concentration_criteria(mechanism: dict) -> List[Tuple[str, str, float]]:
    """抽含量/浓度判据。仅当单位是 mg/L 或 ppm、且同一句点明物质时才返回。

    库中大量"低于2%""超过5%"这类百分数既没点明物质、单位也与 evidence 的
    mg/L 数值不同，强行绑定会给出错误判断，故不纳入。
    """
    texts = [mechanism.get("description", "")] + list(mechanism.get("influencing_factors") or [])
    out: List[Tuple[str, str, float]] = []
    for text in texts:
        for sentence in re.split(r"(?<=[。；;])", str(text)):
            matches = _CONC_CRIT_RE.findall(sentence)
            if not matches:
                continue
            field = next((f for keyword, f in _SPECIES_FIELD if keyword in sentence), None)
            if field is None:
                continue
            for operator, value, _unit in matches:
                out.append((field, _OP_NORMALIZE.get(operator, ">"), float(value)))
    return out


def rank_candidates(mechanisms: List[dict], task_input: dict,
                    parsed: dict) -> List[Tuple[dict, List[str]]]:
    """用条款判据给候选重新排序；返回 [(候选, 判定依据说明)]。

    只影响结论里"主导机理"的选择，不改动任何 step.result。
    """
    evidence_blob = " ".join(str(task_input.get(k) or "")
                             for k in ("operating_condition", "field_evidence"))
    ph_value = (parsed.get("evidence") or {}).get("ph")

    scored: List[Tuple[int, int, dict, List[str]]] = []
    for index, mechanism in enumerate(mechanisms):
        delta = 0
        notes: List[str] = []
        for item in _monitor_items(mechanism):
            if _positive_mention(item, evidence_blob):
                delta += 2
                notes.append(f"现场数据涉及本条款监测项「{item}」")
        for operator, threshold in _ph_criteria(mechanism):
            if ph_value is None:
                continue
            violated = ((operator in ("低于", "小于") and ph_value >= threshold)
                        or (operator in ("高于", "大于") and ph_value <= threshold))
            if violated:
                delta -= 3
                notes.append(f"条款判据为 pH {operator} {threshold}，实测 pH={ph_value}，不满足")
            else:
                delta += 2
                notes.append(f"实测 pH={ph_value} 满足条款判据 pH {operator} {threshold}")

        # 温度阈值判据（同一机理多条时累计后截断，避免过度惩罚）
        temp_c = parsed.get("temperature_c")
        if temp_c is not None:
            temp_delta = 0
            for symbol, threshold in _temperature_criteria(mechanism):
                ok = _holds(symbol, temp_c, threshold)
                temp_delta += 2 if ok else -2
                notes.append(f"条款判据 温度{symbol}{threshold:g}℃，实测 {temp_c:g}℃，"
                             f"{'满足' if ok else '不满足'}")
            delta += max(-3, min(2, temp_delta))

        # 含量/浓度阈值判据（仅在单位与物质都能对应时才有值）
        for field, symbol, threshold in _concentration_criteria(mechanism):
            measured = (parsed.get("evidence") or {}).get(field)
            if measured is None:
                continue
            ok = _holds(symbol, float(measured), threshold)
            delta += 2 if ok else -2
            notes.append(f"条款判据 {field} {symbol} {threshold:g}，实测 {measured}，"
                         f"{'满足' if ok else '不满足'}")

        scored.append((-delta, index, mechanism, notes))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [(mechanism, notes) for _, _, mechanism, notes in scored]


# ---------------------------------------------------------------- 规则决策器
class RulePlanner:
    """确定性的专家式决策器：先识别机理，再检索鉴别依据，最后判严重性。

    不需要大模型，适合批量生成轨迹与回归测试；决策全部由工具真实返回驱动，
    不预设任何条款内容。
    """

    def __init__(self, annotator: str = "rule-planner"):
        self.annotator = annotator

    def __call__(self, task_input: dict, history: List[Step]) -> dict:
        parsed = parse_input(task_input)
        material = str(task_input.get("material") or "").strip()
        medium = task_input.get("medium") or []
        if isinstance(medium, str):
            medium = [medium]

        question = str(task_input.get("question") or "")
        evidence = parsed["evidence"]
        asks_attribution = bool(re.search(r"是否|是不是|能否|能不能|归因|是.{0,12}(?:导致|引起|造成)", question))
        # 现场明确未见减薄且未见裂纹 —— 与腐蚀减薄类、开裂类机理的形态相冲突
        negative_form = (evidence.get("wall_thinning") is False
                         and evidence.get("crack_found") is False)

        # ---- 第 1 步：识别损伤机理 ----
        if not history:
            args: Dict[str, Any] = {"material": material, "medium": list(medium)}
            if parsed["temperature_c"] is not None:
                args["temperature_c"] = parsed["temperature_c"]
            if parsed["equipment_type"]:
                args["equipment_type"] = parsed["equipment_type"]
            if parsed["evidence"]:
                args["evidence"] = parsed["evidence"]
            return {
                "thought": "先用材质、介质、温度和现场证据筛出候选损伤机理。",
                "tool": "damage_mechanism_query",
                "args": args,
            }

        first = history[0]
        if first.blocked:
            return self._final(task_input, history, special_type="out_of_domain")

        resp = first.result or {}
        if resp.get("status") == "out_of_domain" or resp.get("in_domain") is False:
            return self._final(task_input, history, special_type="out_of_domain")
        if resp.get("status") != "ok":
            return self._final(task_input, history, special_type="insufficient_info")

        mechanisms = (resp.get("result") or {}).get("mechanisms") or []
        if not mechanisms:
            # 候选被证据全部排除 -> 排除型
            return self._final(task_input, history, special_type="exclusion")

        # ---- 排除型：问的是归因，而现场形态明确否定减薄与裂纹 ----
        if asks_attribution and negative_form:
            if len(history) == 1:
                names = " ".join(m.get("name", "") for m in mechanisms[:2])
                return {
                    "thought": "问的是归因，但定点测厚未见减薄、检测未见裂纹，先核对候选机理的损伤形态。",
                    "tool": "standard_clause_search",
                    "args": {"keyword": names, "knowledge_type": "damage_mechanism", "top_k": 3},
                }
            return self._final(task_input, history, special_type="exclusion")

        # ---- 信息不足型：多种介质同时存在，却没有任何现场证据 ----
        if len(history) == 1 and len(medium) >= 2 and not evidence and not asks_attribution:
            return self._final(task_input, history, special_type="insufficient_info")

        # ---- 第 2 步：有多个候选时，检索鉴别依据 ----
        if len(history) == 1 and len(mechanisms) >= 2:
            names = [m.get("name", "") for m in mechanisms[:2]]
            keyword = " ".join(n for n in names if n)
            return {
                "thought": f"候选不止一个（{ '、'.join(names) }），检索区分它们所需的条款依据。",
                "tool": "standard_clause_search",
                "args": {"keyword": keyword, "knowledge_type": "damage_mechanism", "top_k": 3},
            }

        # ---- 第 3 步：判严重性 ----
        has_rbi_step = any(step.tool == "rbi_lookup" for step in history)
        if not has_rbi_step:
            # 用条款判据选出主导机理，再用它的名字去查等级
            ranked = rank_candidates(mechanisms, task_input, parsed)
            top = ranked[0][0].get("name", "")
            args = {"equipment_type": parsed["equipment_type"] or "容器", "material": material}
            if top:
                args["mechanism"] = top
            if medium:
                args["medium"] = list(medium)
            if parsed["temperature_c"] is not None:
                args["temperature_c"] = parsed["temperature_c"]
            if parsed["pressure_mpa"] is not None:
                args["pressure_mpa"] = parsed["pressure_mpa"]
            if parsed["service_years"] is not None:
                args["service_years"] = parsed["service_years"]
            return {
                "thought": f"主导机理倾向{top}，查它的风险等级与检验周期。",
                "tool": "rbi_lookup",
                "args": args,
            }

        return self._final(task_input, history)

    # ---------------- 结论生成（全部取自工具返回，不添加条款外知识） ----------------
    def _final(self, task_input: dict, history: List[Step],
               special_type: Optional[str] = None) -> dict:
        parsed = parse_input(task_input)
        dm = next((s.result for s in history if s.tool == "damage_mechanism_query" and not s.blocked), {})
        search = next((s.result for s in history if s.tool == "standard_clause_search" and not s.blocked), {})
        rbi = next((s.result for s in history if s.tool == "rbi_lookup" and not s.blocked), {})

        basis: List[str] = []
        for step in history:
            for cid in _basis_of(step.result):
                if cid not in basis:
                    basis.append(cid)

        # 1) 超出条款覆盖范围
        if special_type == "out_of_domain":
            message = (dm or {}).get("message") or "当前条款库不能覆盖该工况。"
            return {
                "thought": "当前条款库不覆盖该工况，不给出机理判定结论。",
                "special_type": "out_of_domain",
                "final_answer": {
                    "conclusion": f"现有条款库无法对该工况给出有依据的损伤机理判定。{message}",
                    # 超范围轨迹不引用任何条款作为结论依据（与标注示范 UG-DEMO-0005 一致）。
                    # 工具返回的 source 仍保留在 steps[].result 里，那是"核对过的条款"，不是结论依据。
                    "basis": [],
                },
            }

        # 2) 信息不足：候选之间无法区分，补齐数据再判
        mechanisms = (dm.get("result") or {}).get("mechanisms") or []
        if special_type == "insufficient_info":
            names = "、".join(m.get("name", "") for m in mechanisms[:3]) or "候选机理"
            discriminator = (dm.get("result") or {}).get("discriminator") or ""
            conclusion = f"现有输入不足以在 {names} 之间判定主导机理。{discriminator}"
            conclusion += "建议按上述判据补充现场数据后重新判定。"
            if basis:
                conclusion += "（依据 " + "、".join(basis) + "）"
            return {
                "thought": "证据不足以区分候选，结论落在补充数据。",
                "special_type": "insufficient_info",
                "final_answer": {"conclusion": conclusion, "basis": basis},
            }

        # 3) 候选被排除 / 证据与形态不符
        if special_type == "exclusion" or not mechanisms:
            excluded = (dm.get("result") or {}).get("excluded") or []
            detail = "；".join(f"{e.get('name')}（{e.get('reason')}）" for e in excluded[:3])
            conclusion = "现有证据不支持把该异常归因于条款库中的腐蚀或开裂机理。"
            if mechanisms:
                names = "、".join(m.get("name", "") for m in mechanisms[:3])
                conclusion += (f"候选机理（{names}）均以减薄、点蚀或开裂为主要损伤形态，"
                               f"而现场定点测厚未见减薄、检测未见裂纹，形态不符。")
            if detail:
                conclusion += f"另有条款因素被排除：{detail}。"
            conclusion += "建议优先排查焊接、制造或仪表等非腐蚀因素，并复核材质与介质输入。"
            if basis:
                conclusion += "（依据 " + "、".join(basis) + "）"
            return {
                "thought": "候选机理与现场形态不符，结论落在排除方向。",
                "special_type": "exclusion",
                "final_answer": {"conclusion": conclusion, "basis": basis},
            }

        # 3) 正常结论：用条款判据重新排序，选出主导机理（不改动任何 step.result）
        ranked = rank_candidates(mechanisms, task_input, parsed)
        top, top_notes = ranked[0]
        ranked_others = [item for item, _ in ranked[1:]]
        name = top.get("name", "")
        parts: List[str] = []
        parts.append(f"主导机理倾向{name}（依据 {top.get('clause_id')}）。")
        if top_notes:
            parts.append("判定依据：" + "；".join(top_notes[:3]) + f"（依据 {top.get('clause_id')}）。")
        morphology = "；".join((top.get("morphology") or [])[:2])
        if morphology:
            parts.append(f"损伤形态：{morphology}。")
        factors = "、".join((top.get("influencing_factors") or [])[:3])
        if factors:
            parts.append(f"主要影响因素：{factors}。")
        if ranked_others:
            others = "、".join(m.get("name", "") for m in ranked_others[:2])
            parts.append(f"不能排除{others}（依据 "
                         + "、".join(m.get("clause_id", "") for m in ranked_others[:2]) + "）。")
        discriminator = (dm.get("result") or {}).get("discriminator")
        if discriminator:
            parts.append(f"仍需补充证据：{discriminator}")

        prevention = "、".join((top.get("prevention") or [])[:3])
        if prevention:
            parts.append(f"建议措施：{prevention}（依据 {top.get('clause_id')}）。")
        detection = "、".join((top.get("detection_methods") or [])[:2])
        if detection:
            parts.append(f"检测建议：{detection}（依据 {top.get('clause_id')}）。")

        hits = (search.get("result") or {}).get("hits") or []
        if hits:
            parts.append(f"鉴别参考：{hits[0].get('clause_id')}《{hits[0].get('title')}》。")

        if rbi.get("status") == "ok":
            result = rbi.get("result") or {}
            parts.append(
                f"风险等级：{result.get('risk_level')}（统一等级 {result.get('risk_level_unified')}）；"
                f"检验周期：{result.get('inspection_interval_year') if result.get('inspection_interval_year') is not None else '无条款依据'}。"
            )
        elif rbi:
            parts.append("风险等级与检验周期：当前条款库无法给出有条款依据的结论。")

        conclusion = "".join(parts)
        return {
            "thought": "证据已足够，给出结论并逐条标注依据。",
            "special_type": special_type,
            "final_answer": {"conclusion": conclusion, "basis": basis},
        }


# ---------------------------------------------------------------- 大模型决策器（可选）
LLM_SYSTEM_PROMPT = """你是承压设备风险研判助手，只能调用给定的三个工具。
每一步只输出一个 JSON 对象，不要输出任何其它文字。两种格式之一：
{"thought":"...", "tool":"工具名", "args":{...}}
{"thought":"...", "final_answer":{"conclusion":"...","basis":["clause_id", ...]}}
规则：
1. 只能使用下列工具，参数名不得改动。
2. basis 只能填工具返回 source 里出现过的 clause_id。
3. 工具返回 status 不是 ok 时，不要编造等级、周期或条款号。
4. final_answer 的 conclusion 中每条断言后都要标注依据。"""


class LLMPlanner:
    """OpenAI 兼容接口的决策器；未配置或解析失败时回落到 RulePlanner 的同一决策。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 registry: ToolRegistry, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.registry = registry
        self.timeout = timeout
        self.fallback = RulePlanner()
        self.parsed_ok = 0
        self.parsed_fail = 0

    def _tool_prompt(self) -> str:
        lines = ["可用工具："]
        for name, func, desc, params in tool_impl.iter_tool_definitions():
            lines.append(f"- {name}: {desc}")
            lines.append(f"  参数: {json.dumps(params, ensure_ascii=False)}")
        return "\n".join(lines)

    def _messages(self, task_input: dict, history: List[Step]) -> List[dict]:
        messages = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT + "\n" + self._tool_prompt()},
            {"role": "user", "content": "用户输入：" + json.dumps(task_input, ensure_ascii=False)},
        ]
        for step in history:
            messages.append({"role": "assistant", "content": json.dumps(
                {"thought": step.thought, "tool": step.tool, "args": step.args}, ensure_ascii=False)})
            messages.append({"role": "user", "content": "工具返回：" + json.dumps(
                {"tool": step.tool, "result": step.result or {"status": "error",
                                                              "in_domain": False, "result": {},
                                                              "source": [], "message": step.observation}},
                ensure_ascii=False)})
        messages.append({"role": "user", "content": "请给出下一步的 JSON 决策。"})
        return messages

    def _chat(self, messages: List[dict]) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        text = (text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text, flags=re.S).strip()
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                obj = json.loads(match.group(0))
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    def __call__(self, task_input: dict, history: List[Step]) -> dict:
        try:
            raw = self._chat(self._messages(task_input, history))
            decision = self._extract_json(raw)
            if not decision:
                raise ValueError("模型输出不是合法 JSON")
            if "final_answer" not in decision:
                if decision.get("tool") not in self.registry.names():
                    raise ValueError(f"模型选择了未注册工具 {decision.get('tool')!r}")
                if not isinstance(decision.get("args", {}), dict):
                    raise ValueError("args 必须是对象")
            self.parsed_ok += 1
            return decision
        except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as exc:
            # 解析失败不中断流程：回落到规则决策器（解析成功率由 parse_report 统计）
            self.parsed_fail += 1
            fallback = self.fallback(task_input, history)
            fallback["thought"] = f"[回落到规则决策器：{exc}] " + fallback.get("thought", "")
            return fallback

    @property
    def parse_success_rate(self) -> float:
        total = self.parsed_ok + self.parsed_fail
        return self.parsed_ok / total if total else 0.0


def build_llm_planner(registry: ToolRegistry) -> Optional[LLMPlanner]:
    """按环境变量构造大模型决策器；未配置返回 None。

    HARNESS_LLM=1 时启用，需要：
      HARNESS_LLM_BASE_URL  (默认 https://dashscope.aliyuncs.com/compatible-mode/v1)
      HARNESS_LLM_API_KEY
      HARNESS_LLM_MODEL     (默认 qwen-plus)
    """
    if os.environ.get("HARNESS_LLM", "").strip() not in ("1", "true", "TRUE", "yes"):
        return None
    api_key = os.environ.get("HARNESS_LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("HARNESS_LLM=1 但缺少 HARNESS_LLM_API_KEY")
    return LLMPlanner(
        base_url=os.environ.get("HARNESS_LLM_BASE_URL",
                                "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        api_key=api_key,
        model=os.environ.get("HARNESS_LLM_MODEL", "qwen-plus"),
        registry=registry,
    )


# =============================================================
# 6. TODO-1：注册真实工具
# =============================================================

def build_registry() -> ToolRegistry:
    """把 tools.py 的三个真实工具注册进来。

    参数表由 tools.TOOL_PARAMETERS 提供，与《工具接口规范》逐项一致（不得增删改名）。
    """
    reg = ToolRegistry()
    for name, func, description, parameters in tool_impl.iter_tool_definitions():
        reg.register(ToolSpec(name=name, func=func, description=description, parameters=parameters))
    return reg


# =============================================================
# 7. TODO-4：批量运行与完整率统计
# =============================================================

def run_batch(inputs: Iterable[dict], planner: Callable, out_trajectories: Optional[Path] = None,
              out_run_log: Optional[Path] = None, annotator: str = "rule-planner",
              max_items: Optional[int] = None) -> dict:
    """批量跑输入，导出轨迹与运行日志，并统计指标(3)需要的口径。"""
    harness = Harness(build_registry())
    records: List[dict] = []
    logs: List[dict] = []
    stats = {"total": 0, "ok": 0, "blocked": 0, "rejected": 0,
             "multi_step": 0, "single_step": 0,
             "exclusion": 0, "insufficient_info": 0, "out_of_domain": 0}

    for index, item in enumerate(inputs, 1):
        if max_items is not None and stats["total"] >= max_items:
            break
        traj_id = item.get("traj_id") or f"AUTO-{index:04d}"
        task_input = item.get("input") if "input" in item else item
        traj = harness.run(traj_id=traj_id, task_input=task_input, planner=planner,
                           annotator=annotator)
        stats["total"] += 1
        logs.append(traj.to_dict())

        if any(step.blocked for step in traj.steps):
            stats["blocked"] += 1
        try:
            record = traj.to_record()
        except DatasetExportError:
            stats["rejected"] += 1
            continue
        stats["ok"] += 1
        stats["multi_step" if record["task_type"] == "multi_step" else "single_step"] += 1
        special = record.get("special_type")
        if special in ("exclusion", "insufficient_info", "out_of_domain"):
            stats[special] += 1
        records.append(record)

    if out_trajectories:
        save_jsonl(out_trajectories, records)
    if out_run_log:
        save_jsonl(out_run_log, logs)
    stats["complete_rate"] = (stats["ok"] / stats["total"]) if stats["total"] else 0.0
    return stats


# =============================================================
# 8. 演示
# =============================================================

DEMO_INPUTS = [
    {
        "traj_id": "DEMO-0001",
        "input": {
            "equipment": "常压塔顶空冷器",
            "material": "碳钢",
            "medium": ["氯化氢", "氯化铵", "湿硫化氢"],
            "operating_condition": "管束入口温度约 110℃，投用 8 年，注水点位于空冷器上游",
            "field_evidence": "塔顶回流罐水样 pH 5.8，氯离子 42 mg/L，铁离子由 1.2 上升至 4.1 mg/L；压降近一月上升约 15%；上次检验未发现明显减薄，未发现裂纹",
            "question": "铁离子上升的主导机理是什么？建议采取什么措施？",
        },
    },
    {
        "traj_id": "DEMO-0002",
        "input": {
            "equipment": "常压塔顶管道",
            "material": "碳钢",
            "medium": ["氯化氢"],
            "operating_condition": "操作温度 95℃，常压",
            "field_evidence": "",
            "question": "碳钢管道在含氯化氢的塔顶物料中，可能发生什么损伤？检测方法是什么？",
        },
    },
    {
        "traj_id": "DEMO-0003",
        "input": {
            "equipment": "加氢反应器出口管道",
            "material": "碳钢",
            "medium": ["含盐水"],
            "operating_condition": "操作温度 600℃",
            "field_evidence": "",
            "question": "该工况下可能发生什么损伤？",
        },
    },
    {
        "traj_id": "DEMO-0004",
        "input": {
            "equipment": "常压塔顶放空管道",
            "material": "碳钢",
            "medium": ["氯化氢", "湿硫化氢"],
            "operating_condition": "操作温度 105℃，投用 3 年",
            "field_evidence": "渗漏点位于焊缝附近；渗漏点周边及上下游各 2 米定点测厚，壁厚正常，未见减薄；宏观检查未见腐蚀产物堆积；未发现裂纹",
            "question": "该渗漏是腐蚀导致的吗？",
        },
    },
    {
        "traj_id": "DEMO-0005",
        "input": {
            "equipment": "常压塔顶冷凝器",
            "material": "碳钢",
            "medium": ["湿硫化氢", "氯化氢"],
            "operating_condition": "操作温度 120℃",
            "field_evidence": "",
            "question": "可能发生什么损伤？",
        },
    },
]


if __name__ == "__main__":
    for stream in (sys.stdout,):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    registry = build_registry()
    harness = Harness(registry)
    llm = build_llm_planner(registry)
    planner = llm or RulePlanner()
    out_dir = SUBMIT_DIR / "runs"

    print("=" * 78)
    print(f"已注册工具：{registry.names()}")
    print(f"决策器：{'LLMPlanner(' + llm.model + ')' if llm else 'RulePlanner（确定性）'}")
    print("=" * 78)

    stats = run_batch(DEMO_INPUTS, planner,
                      out_trajectories=out_dir / "demo_trajectories.jsonl",
                      out_run_log=out_dir / "demo_run_log.jsonl",
                      annotator="harness-demo")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    print("\n--- 逐条检查点 ---")
    for item in DEMO_INPUTS:
        traj = harness.run(traj_id=item["traj_id"], task_input=item["input"], planner=planner,
                           annotator="harness-demo")
        record = traj.to_record()
        print(f"{record['traj_id']}: {record['task_type']:11s} "
              f"special={record.get('special_type') or '-':18s} "
              f"steps={len(record['steps'])} basis={len(record['final_answer']['basis'])}")
        print(f"    结论：{record['final_answer']['conclusion'][:88]}...")
        for step in record["steps"]:
            print(f"    - 步骤{step['step']} {step['tool']}：{step['observation'][:66]}")

    print("\n--- 轨迹完整率（含被拦截步骤的运行日志口径）---")
    print(f"总数 {stats['total']}，入集 {stats['ok']}，被拦截 {stats['blocked']}，"
          f"未入集 {stats['rejected']}，完整率 {stats['complete_rate']:.2%}")
    print(f"多步 {stats['multi_step']}，单步 {stats['single_step']}；"
          f"排除型 {stats['exclusion']}，信息不足 {stats['insufficient_info']}，超范围 {stats['out_of_domain']}")
    if llm:
        print(f"模型输出解析成功率：{llm.parse_success_rate:.2%}")

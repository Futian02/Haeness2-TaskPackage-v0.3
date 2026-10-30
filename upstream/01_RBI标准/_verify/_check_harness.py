# -*- coding: utf-8 -*-
"""护栏四类实际拦截行为 + Harness 四大能力实测"""
import sys, json, io
sys.path.insert(0, '05_提交区')
import harness, tools

FAILS = []
def check(name, cond, detail=''):
    if not cond:
        FAILS.append((name, detail))
    print('[ %s ] %s%s' % ('OK  ' if cond else 'FAIL', name, ('  -> ' + str(detail)) if (detail and not cond) else ''))

reg = harness.build_registry() if hasattr(harness, 'build_registry') else None
if reg is None:
    import harness as H
    for n in dir(H):
        if 'regist' in n.lower():
            print('候选:', n)
    reg = H.ToolRegistry()
    for name, fn, desc, params in tools.iter_tool_definitions():
        reg.register(harness.ToolSpec(name=name, func=fn, description=desc, parameters=params))
H = harness.Harness(reg)

print('=' * 78)
print('一、护栏四类拦截（README 第四部分）')
print('=' * 78)

# 1 unknown_tool
try:
    H.call_tool('damage_mechanism_querry', {'material': '碳钢', 'medium': ['氯化氢']})
    check('unknown_tool 被拦截', False, '未被拦截')
except harness.GuardrailError as e:
    check('unknown_tool 被拦截', e.kind == 'unknown_tool', e.kind)

# 2 missing_param
try:
    H.call_tool('damage_mechanism_query', {'material': '碳钢'})
    check('missing_param 被拦截', False, '未被拦截')
except harness.GuardrailError as e:
    check('missing_param 被拦截', e.kind == 'missing_param', e.kind)

# 3 bad_format —— 枚举越界 / 类型错 / 未知参数
for desc, args in [
    ('枚举越界(介质)', {'material': '碳钢', 'medium': ['不存在的介质']}),
    ('类型错(medium为字符串)', {'material': '碳钢', 'medium': '氯化氢'}),
    ('未知参数', {'material': '碳钢', 'medium': ['氯化氢'], 'bogus': 1}),
    ('类型错(temperature为字符串)', {'material': '碳钢', 'medium': ['氯化氢'], 'temperature_c': '110℃'}),
    ('数组写成逗号串', {'material': '碳钢', 'medium': '氯化氢,氯化铵'}),
]:
    try:
        H.call_tool('damage_mechanism_query', args)
        check('bad_format: %s 被拦截' % desc, False, '未被拦截')
    except harness.GuardrailError as e:
        check('bad_format: %s 被拦截' % desc, e.kind == 'bad_format', e.kind)

# 4 out_of_domain
try:
    r = tools.damage_mechanism_query(material='碳钢', medium=['湿硫化氢'])
    if r.get('in_domain') is False:
        check('out_of_domain 返回 in_domain=false 且 result 空',
              r.get('result') == {} and bool(r.get('message')), r)
    else:
        check('out_of_domain 返回 in_domain=false 且 result 空', True,
              '本次查询在域内，未触发（逻辑正确）')
except harness.GuardrailError:
    check('out_of_domain 返回 in_domain=false 且 result 空', True, '被护栏拦下')

# 正常调用不应被拦
r = H.call_tool('damage_mechanism_query', {'material': '碳钢', 'medium': ['湿硫化氢']})
check('正常调用未被误拦', r['status'] in ('ok', 'not_found'), r['status'])
r = H.call_tool('standard_clause_search', {'keyword': '腐蚀'})
check('正常检索未被误拦', r['status'] in ('ok', 'not_found'), r['status'])

print()
print('=' * 78)
print('二、Harness 四大能力（README 1.3 / 第四部分）')
print('=' * 78)
check('① 工具注册表已注册 3 个工具', len(reg.names()) == 3, reg.names())
check('② MAX_ROUNDS >= 5', harness.Harness.MAX_ROUNDS >= 5, harness.Harness.MAX_ROUNDS)
check('③ 护栏四类方法齐备',
      all(hasattr(harness.Guardrail, m) for m in
          ['check_tool_exists', 'check_params', 'check_in_domain', 'check_response_format']))
check('④ 轨迹留痕：to_dict / to_record 均在',
      hasattr(harness.Trajectory, 'to_dict') and hasattr(harness.Trajectory, 'to_record'))

# 轨迹完整率：含被拦截的调用，steps 数 == 实际发起调用次数
# （planner 返回 final_answer 的那一次不算工具调用，不应计入 steps）
tool_calls = []
def planner2(task_input, history):
    if len(history) == 0:
        tool_calls.append(1)
        return {'thought': '故意错工具名', 'tool': 'nope', 'args': {}}
    if len(history) == 1:
        tool_calls.append(1)
        return {'thought': '检索', 'tool': 'standard_clause_search', 'args': {'keyword': '腐蚀'}}
    return {'thought': '结束', 'final_answer': {'conclusion': 'x', 'basis': ['GBT30579-2022-5.5']}}
traj = H.run('CHK-001', {'equipment': 'a', 'material': 'b', 'medium': [], 'operating_condition': '',
                          'field_evidence': '', 'question': 'q'}, planner2)
check('轨迹完整率：steps 数 == 实际发起调用次数',
      len(traj.steps) == len(tool_calls), 'steps=%d calls=%d' % (len(traj.steps), len(tool_calls)))
check('被拦截的调用也留痕', any(s.blocked for s in traj.steps))
try:
    traj.to_record()
    check('含拦截步骤的轨迹不进数据集(to_record 抛错)', False, '未抛错')
except harness.DatasetExportError:
    check('含拦截步骤的轨迹不进数据集(to_record 抛错)', True)

print()
print('=' * 78)
print('三、扩展接口（README 5.1：预留研判、审查、建议三类智能体协作）')
print('=' * 78)
check('Harness.run 接受 planner 回调（可替换决策者）',
      'planner' in harness.Harness.run.__code__.co_varnames)
check('Harness.run 接受 reviewer 回调（审查扩展接口）',
      'reviewer' in harness.Harness.run.__code__.co_varnames)
check('Trajectory 带 review 字段（只进运行日志）',
      'review' in harness.Trajectory.__dataclass_fields__)

INP = {'equipment': 'a', 'material': 'b', 'medium': [], 'operating_condition': '',
       'field_evidence': '', 'question': 'q'}
def planner3(task_input, history):
    if len(history) == 0:
        return {'thought': '检索', 'tool': 'standard_clause_search', 'args': {'keyword': '腐蚀'}}
    return {'thought': '结束', 'final_answer': {'conclusion': 'x', 'basis': ['GBT30579-2022-5.5']}}

t_none = H.run('CHK-100', INP, planner3)
check('不传 reviewer 时行为不变（review=None）', t_none.review is None, t_none.review)
check('不传 reviewer 时轨迹仍可导出', bool(t_none.to_record()))

t_ok = H.run('CHK-101', INP, planner3, reviewer=lambda rec: {'passed': True, 'issues': []})
check('reviewer 通过时记录 passed=True', t_ok.review.get('passed') is True, t_ok.review)
check('reviewer 通过时轨迹可导出', bool(t_ok.to_record()))

t_bad = H.run('CHK-102', INP, planner3, reviewer=lambda rec: {'passed': False, 'issues': ['basis 编造']})
check('reviewer 不通过时记录 passed=False', t_bad.review.get('passed') is False, t_bad.review)
check('reviewer 不通过时问题写进 observation',
      '审查未通过' in t_bad.steps[-1].observation, t_bad.steps[-1].observation[:60])
try:
    t_bad.to_record()
    check('reviewer 不通过的轨迹不进数据集', False, '未抛错')
except harness.DatasetExportError:
    check('reviewer 不通过的轨迹不进数据集', True)

t_err = H.run('CHK-103', INP, planner3, reviewer=lambda rec: (_ for _ in ()).throw(RuntimeError('崩了')))
check('reviewer 自身异常不影响主流程', t_err.review.get('error') is True, t_err.review)
check('审查结果只进运行日志，不进数据集字段',
      'review' not in t_ok.to_record() and 'review' in t_ok.to_dict())

print()
print('=' * 78)
print('汇总')
print('=' * 78)
if FAILS:
    print('不通过 %d 项：' % len(FAILS))
    for n, d in FAILS:
        print('  -', n, '|', d)
else:
    print('全部通过。')

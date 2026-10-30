# -*- coding: utf-8 -*-
"""B1 严格审查：逐条重新实跑，与清单记录比对。"""
import json, collections, sys
sys.path.insert(0, '05_提交区')
import tools

scen = json.load(open('01_RBI标准/_verify/轨迹场景清单.json', encoding='utf-8'))
_, agg = tools.load_clauses()
DM = {r['title']: r for r in agg['damage_mechanism']}
allm = sorted(DM.keys())

FAILS = []
def check(name, cond, detail=''):
    if not cond:
        FAILS.append((name, detail))
    print('[ %s ] %s%s' % ('OK  ' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if (detail and not cond) else ''))

print('=' * 84)
print('审查 1：expect_mechs / actual_mechs 与工具真实返回是否一致')
print('=' * 84)
mismatch = []
for x in scen:
    r = tools.damage_mechanism_query(material=x['material'], medium=x['medium'],
                                     temperature_c=x['temperature_c'],
                                     equipment_type=x['equipment_type'])
    real = [m['name'] for m in (r['result'].get('mechanisms') or [])] if r['result'] else []
    x['_real'] = real
    x['_status'] = r['status']
    # expect_mechs 应等于真实返回
    if x['expect_mechs'] != real:
        mismatch.append((x['sid'], x['expect_mechs'][:3], real[:3]))
check('expect_mechs 与工具真实返回一致', not mismatch,
      '%d 条不一致，例：%s' % (len(mismatch), mismatch[:3]))

# actual_mechs 字段（116 条有）与 expect_mechs 的关系
stale = [x['sid'] for x in scen if 'actual_mechs' in x and x['actual_mechs'] != x['_real']]
check('actual_mechs 字段无过期值', not stale, stale[:5])

print()
print('=' * 84)
print('审查 2：状态语义（kind 与查询结果是否自洽）')
print('=' * 84)
prob = []
for x in scen:
    k, st = x['kind'], x['_status']
    if k == 'out_of_domain' and st != 'out_of_domain':
        prob.append((x['sid'], '应 out_of_domain', st))
    if k != 'out_of_domain' and st != 'ok':
        prob.append((x['sid'], '应 ok', st))
check('kind 与查询状态自洽', not prob, prob[:5])

# exclusion 型：必须有候选才谈得上排除
exc = [x for x in scen if x['kind'] == 'exclusion']
check('排除型都有候选机理（否则无从排除）',
      all(x['_real'] for x in exc),
      [x['sid'] for x in exc if not x['_real']][:5])

# insufficient_info 型：也应有候选（要说明"缺什么才能区分"）
ins = [x for x in scen if x['kind'] == 'insufficient_info']
check('信息不足型都有候选机理', all(x['_real'] for x in ins),
      [x['sid'] for x in ins if not x['_real']][:5])

print()
print('=' * 84)
print('审查 3：target_mech / fallback_hits 是否自洽')
print('=' * 84)
tbad = []
for x in scen:
    tm = x.get('target_mech')
    if not tm:
        continue
    if tm not in DM:
        tbad.append((x['sid'], 'target_mech 不在库中', tm)); continue
    want = DM[tm]['clause_id']
    hits = x.get('fallback_hits') or []
    if want not in hits:
        tbad.append((x['sid'], 'fallback_hits 未含目标条款', (tm, want, hits[:3])))
    # target_mech 的语义是「第2步兜底检索要找到的目标机理」，
    # 它本来就不必出现在第1步 damage_mechanism_query 的返回里 —— 那些机理的
    # applicable_conditions.medium 为空，按介质匹配必然查不到。
    # 因此这里只校验兜底检索可达，不校验它是否在第1步返回中。
check('target_mech 与 fallback_hits 自洽', not tbad, tbad[:5])

# 兜底检索的实测复验
frbad = []
for x in scen:
    tm = x.get('target_mech')
    if not tm:
        continue
    sr = tools.standard_clause_search(keyword=tm, knowledge_type='damage_mechanism', top_k=5)
    hits = [h['clause_id'] for h in (sr['result'].get('hits') or [])] if sr['result'] else []
    if DM[tm]['clause_id'] not in hits:
        frbad.append((x['sid'], tm, hits[:3]))
check('兜底检索复验：目标机理现在仍可命中', not frbad, frbad[:5])

print()
print('=' * 84)
print('审查 4：机理覆盖是否仍然 82/82')
print('=' * 84)
hit = set()
for x in scen:
    hit.update(x['_real'])
    if x.get('target_mech'):
        hit.add(x['target_mech'])
    hit.update(x.get('expect_mechs') or [])
missing = [m for m in allm if m not in hit]
check('损伤机理覆盖 82/82', not missing, missing)

print()
print('=' * 84)
print('审查 5：雷同度（两层）')
print('=' * 84)
def fs(x):
    return json.dumps({'eq': x['equipment_type'], 'm': x['material'], 'md': x['medium'],
                       't': x['temperature_c'], 'p': x['equipment']},
                      ensure_ascii=False, sort_keys=True)
def es(x):
    return json.dumps({'ev': x['field_evidence'], 'q': x['question']},
                      ensure_ascii=False, sort_keys=True)
d1 = {k: v for k, v in collections.Counter(fs(x) for x in scen).items() if v > 1}
d2 = {k: v for k, v in collections.Counter(es(x) for x in scen).items() if v > 1}
check('「工况+部位」无重复', not d1, list(d1.items())[:3])
check('「证据+问题」无重复', not d2, list(d2.items())[:3])

# 文本级雷同：问题句式
qs = collections.Counter(x['question'] for x in scen)
qd = {k: v for k, v in qs.items() if v > 1}
print('     [信息] 相同问句 %d 组' % len(qd))
for k, v in sorted(qd.items(), key=lambda x: -x[1])[:5]:
    print('        x%d %s' % (v, k[:52]))

print()
print('=' * 84)
print('审查 6：枚举合法性（材质/介质/设备类型是否都在 enums 内）')
print('=' * 84)
enums = tools.load_enums()
bad = []
for x in scen:
    if x['material'] not in enums['material']:
        bad.append((x['sid'], 'material', x['material']))
    for m in x['medium']:
        if m not in enums['medium']:
            bad.append((x['sid'], 'medium', m))
    if x['equipment_type'] not in enums['equipment_type']:
        bad.append((x['sid'], 'equipment_type', x['equipment_type']))
check('枚举值全部合法', not bad, bad[:5])

print()
print('=' * 84)
print('审查 7：必填字段与 Schema 对齐')
print('=' * 84)
# trajectory.schema.json 的 input 六字段
need = ['equipment', 'material', 'medium', 'operating_condition', 'field_evidence', 'question']
miss = [x['sid'] for x in scen if not all(x.get(k) for k in
         ['equipment', 'material', 'medium', 'temperature_c', 'field_evidence', 'question'])]
check('清单字段可映射到 Schema 的 input 六字段', not miss, miss[:5])
# operating_condition 需要在 B2 由温度+年限合成，检查是否有足够信息
no_cond = [x['sid'] for x in scen if not x.get('temperature_c') is not None]
print('     [信息] 缺 temperature_c 的: %d 条' % len(no_cond))

print()
print('=' * 84)
print('审查 8：tools 声明与实际可达性')
print('=' * 84)
# 每条声明的 tools 是否都能真正调用成功（rbi_lookup 需要库中真实机理名）
tb = []
for x in scen:
    if 'rbi_lookup' in x['tools']:
        # rbi_lookup 的 mechanism 必须是库中真实机理
        mechs = x['_real']
        if not mechs:
            tb.append((x['sid'], '声明 rbi_lookup 但无可用机理名'))
        elif not any(m in DM for m in mechs):
            tb.append((x['sid'], '候选机理都不在库中'))
check('声明 rbi_lookup 的场景都有可用机理名', not tb, tb[:5])

cnt = collections.Counter(t for x in scen for t in x['tools'])
print('     [信息] 工具使用次数:', dict(cnt))

print()
print('=' * 84)
print('汇总')
print('=' * 84)
if FAILS:
    print('不通过 %d 项：' % len(FAILS))
    for n, d in FAILS:
        print('  -', n, '|', d)
else:
    print('全部通过。')

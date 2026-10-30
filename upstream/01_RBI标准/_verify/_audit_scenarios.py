# -*- coding: utf-8 -*-
"""B1 最终校验：场景清单的自查报告。"""
import json, collections, sys
sys.path.insert(0, '05_提交区')
import tools

scen = json.load(open('01_RBI标准/_verify/轨迹场景清单.json', encoding='utf-8'))
_, agg = tools.load_clauses()
allm = sorted(set(r['title'] for r in agg['damage_mechanism']))

print('=' * 78)
print('B1 场景清单最终校验')
print('=' * 78)
print('总数:', len(scen))
print('分类:', dict(collections.Counter(x['kind'] for x in scen)))
print()

# 1. 每条重新实跑，确认 status 与 kind 语义一致
prob = []
for x in scen:
    r = tools.damage_mechanism_query(material=x['material'], medium=x['medium'],
                                     temperature_c=x['temperature_c'],
                                     equipment_type=x['equipment_type'])
    st = r['status']
    x['verified_status'] = st
    if x['kind'] == 'out_of_domain' and st != 'out_of_domain':
        prob.append((x['sid'], '应 out_of_domain', st))
    if x['kind'] != 'out_of_domain' and st != 'ok':
        prob.append((x['sid'], '应 ok', st))
print('1. 状态语义校验（逐条实跑）:', '全部通过' if not prob else prob)

# 2. 兜底检索型场景：目标机理必须能被 standard_clause_search 命中
miss = []
for x in scen:
    if not x.get('target_mech'):
        continue
    sr = tools.standard_clause_search(keyword=x['target_mech'], knowledge_type='damage_mechanism', top_k=5)
    hits = [h['clause_id'] for h in (sr['result'].get('hits') or [])] if sr['result'] else []
    dm = [r for r in agg['damage_mechanism'] if r['title'] == x['target_mech']]
    want = dm[0]['clause_id'] if dm else None
    if want and want not in hits:
        miss.append((x['sid'], x['target_mech'], hits))
print('2. 兜底检索型场景的目标机理可命中:', '全部通过' if not miss else miss)

# 3. 机理覆盖
hit = set()
for x in scen:
    hit.update(x.get('expect_mechs') or [])
    if x.get('target_mech'):
        hit.add(x['target_mech'])
print('3. 损伤机理覆盖: %d/%d' % (len(hit & set(allm)), len(allm)),
      '未覆盖:', [m for m in allm if m not in hit])

# 4. 雷同度：完全重复的 args
argsets = collections.Counter(json.dumps(
    {'m': x['material'], 'md': x['medium'], 't': x['temperature_c'],
     'eq': x['equipment_type']}, ensure_ascii=False, sort_keys=True) for x in scen)
dup = {k: v for k, v in argsets.items() if v > 1}
print('4. 工况组合重复:', len(dup), '组' if dup else '组（零重复）')
for k, v in sorted(dup.items(), key=lambda x: -x[1])[:8]:
    print('     x%d %s' % (v, k))

# 5. 覆盖维度
print()
print('5. 覆盖维度:')
print('   装置:', len(set(x['plant'] for x in scen)), '种')
print('   部位:', len(set(x['equipment'] for x in scen)), '种')
print('   材质:', len(set(x['material'] for x in scen)), '种 ->', sorted(set(x['material'] for x in scen)))
print('   介质:', len(set(m for x in scen for m in x['medium'])), '种')
print('   设备:', dict(collections.Counter(x['equipment_type'] for x in scen)))
print('   温度档:', sorted(set(x['temperature_c'] for x in scen)))

# 6. sid 唯一
ids = [x['sid'] for x in scen]
print()
print('6. sid 唯一:', len(ids) == len(set(ids)), '(%d 条)' % len(ids))

# 7. 每个场景的字段完整性
bad = [x['sid'] for x in scen if not all(x.get(k) for k in
         ['equipment', 'material', 'medium', 'temperature_c', 'field_evidence', 'question', 'tools'])]
print('7. 必填字段完整:', '全部通过' if not bad else bad)

json.dump(scen, open('01_RBI标准/_verify/轨迹场景清单.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('已回写（含 verified_status 字段）')

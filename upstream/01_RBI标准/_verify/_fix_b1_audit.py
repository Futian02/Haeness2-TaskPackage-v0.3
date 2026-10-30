# -*- coding: utf-8 -*-
"""
B1 审查修复：修 4 个缺陷
  缺陷1（36 条）：SC-F 现象检索型场景的 expect_mechs 全为空 —— 生成时未跑工具。
  缺陷2（55 条）：target_mech 场景的 fallback_hits 全为空 —— 未实测兜底检索。
  缺陷3（15 条）：actual_mechs 是改材质前的旧值。
  缺陷4（1 条）：SC-C13 的 target_mech 写作「碱性水腐蚀」，库里实际是「碱腐蚀」。
"""
import json, collections, sys
sys.path.insert(0, '05_提交区')
import tools

P = '01_RBI标准/_verify/轨迹场景清单.json'
scen = json.load(open(P, encoding='utf-8'))
_, agg = tools.load_clauses()
DM = {r['title']: r for r in agg['damage_mechanism']}

print('=== 缺陷4：修正错误的机理名 ===')
for x in scen:
    tm = x.get('target_mech')
    if tm == '碱性水腐蚀':
        x['target_mech'] = '碱腐蚀'
        print('  SC-C13: 碱性水腐蚀 -> 碱腐蚀')

print()
print('=== 缺陷1 + 缺陷2 + 缺陷3：逐条重跑并回填 ===')
fixed_fh = 0
fixed_em = 0
for x in scen:
    # 缺陷3：actual_mechs 一律以实跑为准
    r = tools.damage_mechanism_query(material=x['material'], medium=x['medium'],
                                     temperature_c=x['temperature_c'],
                                     equipment_type=x['equipment_type'])
    real = [m['name'] for m in (r['result'].get('mechanisms') or [])] if r['result'] else []
    x['actual_mechs'] = real
    x['actual_status'] = r['status']
    x['has_discriminator'] = bool(r['result'].get('discriminator')) if r['result'] else False

    # 缺陷1：expect_mechs 对齐真实返回
    if x['expect_mechs'] != real:
        x['expect_mechs'] = real
        fixed_em += 1

    # 缺陷2：target_mech 场景必须实测兜底检索
    tm = x.get('target_mech')
    if tm:
        if tm not in DM:
            print('  !! %s 的 target_mech %r 不在库中' % (x['sid'], tm))
            continue
        sr = tools.standard_clause_search(keyword=tm, knowledge_type='damage_mechanism', top_k=5)
        hits = [h['clause_id'] for h in (sr['result'].get('hits') or [])] if sr['result'] else []
        if x.get('fallback_hits') != hits:
            x['fallback_hits'] = hits
            fixed_fh += 1
        if DM[tm]['clause_id'] not in hits:
            print('  !! %s 兜底检索未命中目标条款 %s（hits=%s）' % (x['sid'], tm, hits))

print('  修正 expect_mechs: %d 条' % fixed_em)
print('  回填 fallback_hits: %d 条' % fixed_fh)

scen = sorted(scen, key=lambda x: x['sid'])
json.dump(scen, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print()
print('已更新 %s' % P)

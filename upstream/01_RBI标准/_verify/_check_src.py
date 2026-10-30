# -*- coding: utf-8 -*-
"""三工具 + Harness 源码合规性检验（对照 README / 工具接口规范）"""
import sys, json, io
sys.path.insert(0, '05_提交区')
import tools

FAILS = []
def check(name, cond, detail=''):
    tag = 'OK  ' if cond else 'FAIL'
    if not cond:
        FAILS.append((name, detail))
    print('[ %s ] %s%s' % (tag, name, ('  -> ' + str(detail)) if (detail and not cond) else ''))

SHELL = {'status', 'in_domain', 'result', 'source', 'message'}

print('=' * 78)
print('一、返回外壳（README 2.5 / 工具接口规范 2.5）')
print('=' * 78)

r = tools.damage_mechanism_query(material='碳钢', medium=['湿硫化氢'])
check('外壳顶层恰为5个字段', set(r.keys()) == SHELL, sorted(r.keys()))
check('status 取值合法', r['status'] in ('ok', 'out_of_domain', 'not_found', 'error'), r['status'])
check('in_domain 为 bool', isinstance(r['in_domain'], bool))
check('result 为 dict', isinstance(r['result'], dict))
check('source 为 list', isinstance(r['source'], list))
check('message 为 str', isinstance(r['message'], str))
check('status=ok 时 source 非空（硬性红线）', not (r['status'] == 'ok' and not r['source']), r['source'])

print()
print('=' * 78)
print('二、damage_mechanism_query（接口规范 2.2）')
print('=' * 78)
EIGHT = ['description', 'morphology', 'affected_materials', 'influencing_factors',
         'susceptible_locations', 'prevention', 'detection_methods', 'related_damages']
mechs = r['result'].get('mechanisms') or []
check('result 含 mechanisms 数组', isinstance(mechs, list) and len(mechs) > 0, len(mechs))
if mechs:
    m = mechs[0]
    check('机理含八段式全部字段', all(k in m for k in EIGHT),
          [k for k in EIGHT if k not in m])
    check('八段式无多余字段', set(m.keys()) <= set(EIGHT + ['name', 'clause_id', 'match_level']),
          [k for k in m.keys() if k not in EIGHT + ['name', 'clause_id', 'match_level']])
    check('description 为 str', isinstance(m['description'], str))
    check('其余七个内容字段为 list', all(isinstance(m[k], list) for k in EIGHT if k != 'description'),
          {k: type(m[k]).__name__ for k in EIGHT if k != 'description'})
    check('含 discriminator 字段', 'discriminator' in r['result'])
    check('含 excluded 字段', 'excluded' in r['result'])
check('source 项只含 4 个允许键',
      all(set(s.keys()) <= {'clause_id', 'standard_code', 'clause_no', 'page'} for s in r['source']),
      [s for s in r['source'] if set(s.keys()) > {'clause_id', 'standard_code', 'clause_no', 'page'}])

print()
print('--- 入参校验 ---')
bad = tools.damage_mechanism_query(material='碳钢', medium='湿硫化氢')
check('medium 写成逗号串 → error', bad['status'] == 'error', bad['status'])
bad = tools.damage_mechanism_query(material='碳钢', medium=['不存在的介质'])
check('介质不在枚举 → error', bad['status'] == 'error', bad['status'])
ok_alias = tools.damage_mechanism_query(material='碳素钢', medium=['湿H2S'])
check('别名可归一化（碳素钢/湿H2S）', ok_alias['status'] == 'ok', ok_alias['status'])

print()
print('=' * 78)
print('三、rbi_lookup（接口规范 2.3）')
print('=' * 78)
r2 = tools.rbi_lookup(equipment_type='换热器', material='碳钢')
check('外壳顶层恰为5个字段', set(r2.keys()) == SHELL, sorted(r2.keys()))
res = r2['result']
if r2['status'] == 'ok':
    for k in ['likelihood', 'consequence', 'risk_level', 'risk_level_unified',
              'inspection_interval_year', 'inspection_methods']:
        check('result 含 %s' % k, k in res)
    check('risk_level_unified 为 L1~L4',
          res.get('risk_level_unified') in (None, 'L1', 'L2', 'L3', 'L4'), res.get('risk_level_unified'))
else:
    # 不给 mechanism 时库中无法定位条款 -> not_found，result 为空是正确行为
    check('无 mechanism 且查不到时 status=not_found', r2['status'] == 'not_found', r2['status'])
    check('not_found 时 result 为空', res == {}, res)
    check('not_found 时 message 说明原因', bool(r2['message'].strip()))
check('status=ok 时 source 非空', not (r2['status'] == 'ok' and not r2['source']))
if res.get('inspection_interval_year') is not None:
    print('     [信息] inspection_interval_year =', res['inspection_interval_year'],
          '| source 条数 =', len(r2['source']))
else:
    print('     [信息] 未返回检验周期（允许：查不到依据应为 null）')

print()
print('--- rbi_lookup 判定路径（2026-10-27 新增）---')
rp = tools.rbi_lookup(equipment_type='换热器', material='碳钢', mechanism='盐酸腐蚀')
check('给 mechanism 时返回判定路径（status=ok）', rp['status'] == 'ok', rp['status'])
check('判定路径带 source（红线：ok 必须有出处）', len(rp['source']) > 0, len(rp['source']))
check('判定路径 source 只含 4 个允许键',
      all(set(s.keys()) <= {'clause_id', 'standard_code', 'clause_no', 'page'} for s in rp['source']))
check('算不出等级时 likelihood 为 null', rp['result'].get('likelihood') is None,
      rp['result'].get('likelihood'))
check('算不出等级时 risk_level_unified 为 null', rp['result'].get('risk_level_unified') is None,
      rp['result'].get('risk_level_unified'))
check('判定路径含 DF 取值依据', 'DF' in rp['result'].get('basis_note', ''),
      rp['result'].get('basis_note', '')[:60])
check('message 说明还需哪些现场信息', '需补充' in rp['message'])

print()
print('=' * 78)
print('四、standard_clause_search（接口规范 2.4）')
print('=' * 78)
r3 = tools.standard_clause_search(keyword='湿硫化氢')
check('外壳顶层恰为5个字段', set(r3.keys()) == SHELL, sorted(r3.keys()))
hits = r3['result'].get('hits')
check('result.hits 为 list', isinstance(hits, list))
if hits:
    h = hits[0]
    check('hit 含 clause_id/title/snippet/score',
          all(k in h for k in ['clause_id', 'title', 'snippet', 'score']),
          sorted(h.keys()))
    check('snippet ≤200 字', all(len(x.get('snippet', '')) <= 200 for x in hits),
          max(len(x.get('snippet', '')) for x in hits))
check('top_k 上限 20',
      len(tools.standard_clause_search(keyword='腐蚀', top_k=100)['result']['hits']) <= 20)
check('top_k 默认 5',
      len(tools.standard_clause_search(keyword='腐蚀')['result']['hits']) <= 5,
      len(tools.standard_clause_search(keyword='腐蚀')['result']['hits']))
bad = tools.standard_clause_search(keyword='')
check('keyword 空 → error', bad['status'] == 'error', bad['status'])
bad = tools.standard_clause_search(keyword='腐蚀', knowledge_type='xxx')
check('knowledge_type 非法 → error', bad['status'] == 'error', bad['status'])

print()
print('=' * 78)
print('五、工具注册表（README 2.1：只有三个，不得增删改名）')
print('=' * 78)
names = [d[0] for d in tools.iter_tool_definitions()]
check('恰好注册 3 个工具', len(names) == 3, names)
check('工具名与规范一致',
      set(names) == {'damage_mechanism_query', 'rbi_lookup', 'standard_clause_search'}, names)

print()
print('=' * 78)
print('六、枚举白名单（enums.json 不得扩充）')
print('=' * 78)
enums = tools.load_enums()
check('material 表非空', len(enums['material']) > 0)
check('medium 表非空', len(enums['medium']) > 0)
check('equipment_type 恰为 6 类', len(enums['equipment_type']) == 6,
      sorted(enums['equipment_type'].keys()))

print()
print('=' * 78)
print('汇总')
print('=' * 78)
if FAILS:
    print('不通过 %d 项：' % len(FAILS))
    for n, d in FAILS:
        print('  -', n, '|', d)
else:
    print('全部通过，无不合规项。')

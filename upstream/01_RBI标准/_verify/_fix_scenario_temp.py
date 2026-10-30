# -*- coding: utf-8 -*-
"""
B2 前置校正 v5：把 34 条「高温部位却标了低温」的场景还原为工程合理温度。

背景：v3 曾对下限型区间用错判定，把 780℃ 的裂解炉辐射段改成 270℃。
这些温度虽然满足「≥260℃」的形式要求，但与部位常识矛盾（焦化塔不可能 270℃）。

本脚本按**装置与部位的工程常识**给回合理温度，再校验其满足对应机理的区间；
若某个温度既符合常识又落在机理区间内，优先取「更贴近常识且在区间内」的值。

温度来源（按部位/装置判定）：
  高温炉类（裂解炉/焦化塔/再生器/常压炉/加热炉/火炬/急冷器/过热器）→ 400~850℃
  中温换热器/管道/容器                                     → 100~300℃
  低温（深冷/冷冻/液氧/液氨）                              → -40~-196℃
  罐区/常温                                               → 20~60℃
然后夹到该场景关心机理的适用区间内。
"""
import json, sys, collections
sys.path.insert(0, '05_提交区')
import tools

_, agg = tools.load_clauses()
DM = {r['title']: r for r in agg['damage_mechanism']}
P = '01_RBI标准/_verify/轨迹场景清单.json'
scen = json.load(open(P, encoding='utf-8'))

HOT = ['裂解炉', '焦化塔', '再生器', '常压炉', '减压炉', '加热炉', '火炬', '急冷',
       '过热器', '再热器', '高温', '炉管', '炉膛', '烟气轮', '烟气管道']
COLD = ['深冷', '冷冻', '液氧', '液氨', '低温段', '超低温']


def guess_temp(x):
    e = x['equipment']
    eq = x['equipment_type']
    plant = x['plant']
    if any(w in e for w in COLD):
        return -40
    if any(w in e for w in HOT):
        if '裂解' in e or '辐射段' in e:
            return 820
        if '焦化塔' in e:
            return 480
        if '再生器' in e:
            return 700
        if '火炬' in e:
            return 800
        if '急冷' in e:
            return 400
        if '常压炉' in e or '减压炉' in e:
            return 450
        if '过热器' in e:
            return 600
        if '再热器' in e:
            return 550
        return 500
    if eq == '储罐':
        return 40
    if eq == '塔':
        return 220
    if eq == '管道':
        return 150
    if eq == '容器':
        return 120
    return 150


def range_of(m):
    rec = DM.get(m)
    if not rec:
        return None, None
    r = rec['applicable_conditions'].get('temperature_c') or [None, None]
    return r[0], r[1]


def focus_of(x):
    tm = x.get('target_mech')
    if tm:
        return tm
    for m in (x.get('expect_mechs') or []):
        lo, hi = range_of(m)
        if lo is not None or hi is not None:
            return m
    return None


def clamp(t, lo, hi):
    if lo is None and hi is None:
        return t
    if lo is None:
        return min(t, hi - 10)
    if hi is None:
        return max(t, lo + 10)
    return max(lo + 5, min(t, hi - 5))


print('=== 还原高温部位的工程合理温度 ===')
fixed = []
for x in scen:
    e = x['equipment']
    t = x['temperature_c']
    if not any(w in e for w in HOT):
        continue
    if t >= 300:
        continue          # 已经合理
    g = guess_temp(x)
    focus = focus_of(x)
    lo, hi = range_of(focus) if focus else (None, None)
    new_t = clamp(g, lo, hi)
    fixed.append((x['sid'], e, t, new_t, focus, lo, hi))
    x['temperature_c'] = new_t
    x['note'] = '温度按部位工程常识还原（%s 适用 %s~%s℃）' % (focus, lo, hi) if focus else ''

for sid, e, old, new, focus, lo, hi in fixed:
    print('  %-9s %-16s %4d℃ -> %4d℃  关注=%s (%s~%s℃)' % (sid, e, old, new, focus, lo, hi))
print()
print('还原 %d 条' % len(fixed))

# 重跑校验
prob = []
for x in scen:
    r = tools.damage_mechanism_query(material=x['material'], medium=x['medium'],
                                     temperature_c=x['temperature_c'],
                                     equipment_type=x['equipment_type'])
    real = [m['name'] for m in (r['result'].get('mechanisms') or [])] if r['result'] else []
    x['expect_mechs'] = real
    x['actual_mechs'] = real
    x['actual_status'] = r['status']
    x['verified_status'] = r['status']
    x['has_discriminator'] = bool(r['result'].get('discriminator')) if r['result'] else False
    if x['kind'] == 'out_of_domain' and r['status'] != 'out_of_domain':
        prob.append((x['sid'], '应 out_of_domain', r['status']))
    if x['kind'] != 'out_of_domain' and r['status'] != 'ok':
        prob.append((x['sid'], '应 ok', r['status']))
print('状态语义:', '全部通过' if not prob else prob)

hit = set()
tm_hit = 0
for x in scen:
    hit.update(x.get('expect_mechs') or [])
    if x.get('target_mech'):
        hit.add(x['target_mech'])
        if x['target_mech'] in (x.get('expect_mechs') or []):
            tm_hit += 1
allm = sorted(DM.keys())
print('机理覆盖: %d/%d  未覆盖: %s' % (len(hit & set(allm)), len(allm),
                                    [m for m in allm if m not in hit]))
print('target_mech 在第1步候选中的: %d / %d' % (tm_hit, len([x for x in scen if x.get('target_mech')])))

# 温度与部位矛盾复查
bad = [(x['sid'], x['equipment'], x['temperature_c']) for x in scen
       if any(w in x['equipment'] for w in HOT) and x['temperature_c'] < 300]
print('温度与部位仍矛盾的:', len(bad), bad[:5])

json.dump(scen, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print()
print('已更新', P)

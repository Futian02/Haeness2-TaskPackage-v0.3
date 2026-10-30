# -*- coding: utf-8 -*-
"""审查 B2 轨迹的「证据—机理」对应质量。

指标好不代表内容对。核心问题：现场证据描述的现象（烧蚀、韧性下降、点蚀…）
是否真的对得上结论里判的机理。若对不上，说明主导机理选错了。

检查项：
  1. 证据关键词与主导机理名称/判据是否有对应；
  2. 结论里是否出现「与上述判据相符」这类空话而证据其实对不上；
  3. out_of_domain 轨迹的结论是否正确地不给机理判定。
"""
import json
import re
import sys
import collections

sys.path.insert(0, '05_提交区')
import tools

_, agg = tools.load_clauses()
DM = {r['title']: r for r in agg['damage_mechanism']}

# 证据现象 → 机理原文判据里应出现的词（查条款原文，而非机理名，
# 因为「汽蚀」的判据写的是「蜂窝状腐蚀坑」而不是「汽蚀」二字）
EV_TO_MECH = [
    (['烧蚀', '灼烫', '回火色', '着火', '阴燃'],
     ['燃烧', '爆炸', '氧化', '烧蚀']),
    (['韧性下降', '变脆'],
     ['脆化', '球化', 'σ相', '475℃', '回火', '再热', '晶粒', '韧性下降']),
    (['分层', '夹层', '鼓泡'],
     ['氢脆', '氢致', '分层', '鼓泡']),
    (['裂纹', '开裂'],
     ['开裂', '裂纹', '断裂', '疲劳', '氢']),
    (['点蚀', '孔蚀', '蚀坑'],
     ['点蚀', '孔蚀', '缝隙', '局部', '浓差', '腐蚀', '蜂窝']),
    (['减薄', '氧化'],
     ['腐蚀', '冲蚀', '冲刷', '磨损', '汽蚀', '减薄', '氧化']),
    (['结垢', '垢下', '过热'],
     ['垢下', '腐蚀', '微生物', '过热', '蒸汽阻滞']),
    (['蜂窝状', '强度升高'],
     ['蜂窝', '汽蚀', '加工硬化', '应变时效']),
    (['碳化层'], ['石墨化', '渗碳']),
    (['熔融金属'], ['液态金属', '液体金属', '脆断']),
    (['辐照'], ['辐照']),
    (['球化现象'], ['球化', '珠光体']),
    (['内外壁温差', '未见减薄'],
     ['氢', '脆', '腐蚀', '疲劳']),
]

recs = [json.loads(l) for l in open('05_提交区/trajectories.jsonl', encoding='utf-8')]

print('=' * 86)
print('审查 A：证据现象与主导机理是否对得上')
print('=' * 86)
bad = []
checked = 0
for r in recs:
    if r.get('special_type') == 'out_of_domain':
        continue
    ev = r['input'].get('field_evidence') or ''
    concl = r['final_answer']['conclusion']
    # 从结论首句取主导机理
    m = re.search(r'主导机理倾向(.+?)。', concl)
    if not m:
        continue
    mech = m.group(1)
    checked += 1
    # 取该机理的条款原文，判断证据现象是否被条款判据覆盖
    cid = None
    for title, rec in DM.items():
        if title == mech:
            cid = rec['clause_id']
            break
    blob = ''
    if cid:
        for rec in agg['damage_mechanism']:
            if rec['clause_id'] == cid:
                d = rec.get('mechanism_detail') or {}
                blob = ' '.join(str(d.get(k) or '') for k in
                                ['description', 'morphology', 'affected_materials',
                                 'related_damages', 'susceptible_locations'])
                break
    hit = False
    has_phenom = False
    for ev_words, mech_words in EV_TO_MECH:
        if any(w in ev for w in ev_words):
            has_phenom = True
            if blob and any(w in blob for w in mech_words):
                hit = True
                break
    if not hit and has_phenom:
        bad.append((r['traj_id'], r['input']['equipment'], ev[:36], mech))

print('  检查 %d 条 | 证据现象与主导机理对不上: %d 条' % (checked, len(bad)))
for b in bad[:20]:
    print('   ✗ %s | %-18s | %-36s -> %s' % b)

print()
print('=' * 86)
print('审查 B：out_of_domain 结论是否正确地不给机理判定')
print('=' * 86)
ood_bad = []
for r in recs:
    if r.get('special_type') != 'out_of_domain':
        continue
    concl = r['final_answer']['conclusion']
    if '主导机理倾向' in concl or '不能排除' in concl:
        ood_bad.append((r['traj_id'], concl[:60]))
print('  超范围轨迹 %d 条 | 误给机理判定: %d 条'
      % (len([r for r in recs if r.get('special_type') == 'out_of_domain']), len(ood_bad)))
for b in ood_bad[:10]:
    print('   ✗', b)

print()
print('=' * 86)
print('审查 C：结论里的「不能排除」候选是否真在候选集里')
print('=' * 86)
cbad = []
for r in recs:
    if r.get('special_type') == 'out_of_domain':
        continue
    concl = r['final_answer']['conclusion']
    # 从「X不能排除，尚需补充判别数据」中精确取候选名
    m = re.search(r'([^。；]+?)不能排除', concl)
    if not m:
        continue
    named = m.group(1)
    step1 = r['steps'][0]['result']
    if step1.get('status') != 'ok':
        continue
    cands = [m2['name'] for m2 in (step1['result'].get('mechanisms') or [])]
    # 机理名本身可能含顿号（如「高含氧气体促发的燃烧、爆炸」），
    # 按「、」切会把一个机理拆成两段，故先做整名匹配，剩余再按空格切
    rest = named
    for n in cands:
        if n in rest:
            rest = rest.replace(n, ' ')
    for n in rest.replace('、', ' ').split():
        if n and n not in cands:
            cbad.append((r['traj_id'], n, cands[:4]))
print('  提及「不能排除」的轨迹中，候选不在第1步返回里的: %d 处' % len(cbad))
for b in cbad[:10]:
    print('   ✗', b)

print()
print('=' * 86)
print('审查 D：结论里引用的条款是否与 basis 一致（逐条）')
print('=' * 86)
dbad = []
for r in recs:
    basis = r['final_answer']['basis']
    concl = r['final_answer']['conclusion']
    for c in basis:
        no = c.split('-')[-1]
        if no not in concl:
            dbad.append((r['traj_id'], c))
print('  basis 有条款未被结论引用: %d 处' % len(dbad))
for b in dbad[:10]:
    print('   ✗', b)

print()
print('汇总：', '全部通过' if not (bad or ood_bad or cbad or dbad)
      else 'A=%d B=%d C=%d D=%d' % (len(bad), len(ood_bad), len(cbad), len(dbad)))

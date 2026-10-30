# -*- coding: utf-8 -*-
"""B2 轨迹内容质量审查：查雷同、查空洞、查真实回溯。"""
import json, collections, sys, re
sys.path.insert(0, '05_提交区')
import tools

recs = [json.loads(l) for l in open('05_提交区/trajectories.jsonl', encoding='utf-8')]
CLAUSES = {}
for l in open('05_提交区/clauses.jsonl', encoding='utf-8'):
    l = l.strip()
    if l:
        r = json.loads(l)
        CLAUSES[r['clause_id']] = r

FAILS = []
def check(name, cond, detail=''):
    if not cond:
        FAILS.append((name, detail))
    print('[ %s ] %s%s' % ('OK  ' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if (detail and not cond) else ''))

print('=' * 86)
print('审查 1：结论正文的雷同度（README 第九部分第 6 条）')
print('=' * 86)
concl = collections.Counter(r['final_answer']['conclusion'] for r in recs)
dup = {k: v for k, v in concl.items() if v > 1}
print('  唯一结论 %d / %d' % (len(concl), len(recs)))
check('结论完全重复的条数为 0', not dup, list(dup.items())[:2])
for k, v in sorted(dup.items(), key=lambda x: -x[1])[:3]:
    print('     x%d %s' % (v, k[:70]))

print()
print('  结论的句式多样性（去掉专有名词后的骨架）：')
skel = collections.Counter()
for r in recs:
    c = r['final_answer']['conclusion']
    c2 = re.sub(r'[《》][^《》]*[《》]', '《X》', c)
    c2 = re.sub(r'(GB/T [\d.\-]+|GBT[\d.\-]+|[\d.]+《[^》]*》)', 'REF', c2)
    c2 = re.sub(r'[A-Za-z0-9\.\-]{6,}', 'X', c2)
    skel[c2[:90]] += 1
print('    唯一骨架 %d / %d' % (len(skel), len(recs)))
for k, v in skel.most_common(4):
    print('      x%-3d %s' % (v, k[:78]))

print()
print('=' * 86)
print('审查 2：结论是否真的引用了 basis（不是空话）')
print('=' * 86)
noref = [r['traj_id'] for r in recs
         if r['final_answer']['basis'] and
         not any(c.split('-')[-1] in r['final_answer']['conclusion'] or c in r['final_answer']['conclusion']
                 for c in r['final_answer']['basis'])]
check('每条结论都显式引用了 basis 条款号', not noref, noref[:6])

empty = [r['traj_id'] for r in recs if not r['final_answer']['conclusion'].strip()]
check('结论非空', not empty, empty[:5])

short = [(r['traj_id'], len(r['final_answer']['conclusion']))
         for r in recs if len(r['final_answer']['conclusion']) < 60]
print('     [信息] 结论短于 60 字的: %d 条' % len(short))
for s in short[:5]:
    print('        ', s)

print()
print('=' * 86)
print('审查 3：steps[].result 是否真的是工具真实返回')
print('=' * 86)
# 抽查：把每条轨迹的第1步 args 重新调用，比对 result 是否一致
import random
random.seed(20261027)
sample = random.sample(recs, 12)
mismatch = []
for r in sample:
    st = r['steps'][0]
    resp = tools.damage_mechanism_query(**st['args'])
    if json.dumps(resp, ensure_ascii=False, sort_keys=True) != \
       json.dumps(st['result'], ensure_ascii=False, sort_keys=True):
        mismatch.append(r['traj_id'])
check('抽查 12 条的第1步 result 与重跑一致（真实返回）', not mismatch, mismatch)

print()
print('=' * 86)
print('审查 4：basis 的 clause_id 是否真实存在且被结论用到')
print('=' * 86)
notexist = [r['traj_id'] for r in recs
            if any(c not in CLAUSES for c in r['final_answer']['basis'])]
check('basis 的 clause_id 全部存在于条款库', not notexist, notexist[:5])

unused = [r['traj_id'] for r in recs
          if r['final_answer']['basis'] and
          not all(c.split('-')[-1] in r['final_answer']['conclusion']
                  for c in r['final_answer']['basis'])]
check('basis 的每一条都在结论中被引用（逐条全引用）', not unused, unused[:6])

sz = collections.Counter(len(r['final_answer']['basis']) for r in recs)
print('     [信息] basis 条数分布:', dict(sorted(sz.items())))

print()
print('=' * 86)
print('审查 5：每步调用是否有独立理由（不能只换参数凑步数）')
print('=' * 86)
samethought = []
for r in recs:
    th = [s['thought'] for s in r['steps']]
    if len(th) > 1 and len(set(th)) != len(th):
        samethought.append(r['traj_id'])
check('同一条轨迹内各步 thought 互不相同', not samethought, samethought[:5])

# 工具序列应体现推理递进
seqs = collections.Counter(tuple(s['tool'] for s in r['steps']) for r in recs)
print('     [信息] 工具序列分布:')
for k, v in seqs.most_common():
    print('        x%-4d %s' % (v, ' -> '.join(k)))

print()
print('=' * 86)
print('审查 6：traj_id 与 input 的雷同度')
print('=' * 86)
inp = collections.Counter(json.dumps(r['input'], ensure_ascii=False, sort_keys=True) for r in recs)
d = {k: v for k, v in inp.items() if v > 1}
check('input 完全重复的为 0', not d, list(d.items())[:2])
print('     [信息] 唯一 input: %d / %d' % (len(inp), len(recs)))

print()
print('=' * 86)
print('汇总')
print('=' * 86)
if FAILS:
    print('不通过 %d 项：' % len(FAILS))
    for n, dd in FAILS:
        print('  -', n, '|', dd)
else:
    print('全部通过。')

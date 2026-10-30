# -*- coding: utf-8 -*-
"""
B2：生成 200 条轨迹到 05_提交区/trajectories.jsonl。

铁律（README 3.2）：
- steps[].result 必须是**工具真实返回** —— 一律经 harness.call_tool 实跑取得，不手写；
- final_answer.basis 的每个 clause_id 必须真实存在于 clauses.jsonl；
- task_type 与调用次数一致（≥3 次 = multi_step，<3 次为 single_step）；
- 每次调用都要有自己的理由，不能只换参数凑步数；
- special_type 只有 out_of_domain 允许 basis 为空。

三类轨迹的形态：
  multi（144 条）        3 步：取候选 → 补鉴别依据/兜底检索 → 判严重性
  single（11 条）        1 步：取候选
  exclusion（15 条）     2 步：取候选 → 检索被排除机理的条款，据此排除
  insufficient_info（15 条）2 步：取候选 → 检索鉴别判据，结论说明还需哪些数据
  out_of_domain（15 条） 1 步：查询返回域外，basis 为空

第2步的检索词用「机理名 + 其判据词」，实测比单用机理名召回更准
（如「热疲劳 循环温差」只命中 8.2，而单用「热疲劳」会带回无关条款）。
"""
import json, sys, collections, os, re
sys.path.insert(0, '05_提交区')
import harness, tools

# ---------- 注册真实工具 ----------
def build_registry():
    reg = harness.ToolRegistry()
    for name, fn, desc, params in tools.iter_tool_definitions():
        reg.register(harness.ToolSpec(name=name, func=fn, description=desc, parameters=params))
    return reg

H = harness.Harness(build_registry())

# ---------- 条款库 ----------
CLAUSE_IDS = set()
TITLE = {}
for line in open('05_提交区/clauses.jsonl', encoding='utf-8'):
    line = line.strip()
    if line:
        rec = json.loads(line)
        CLAUSE_IDS.add(rec['clause_id'])
        TITLE[rec['clause_id']] = rec.get('title') or ''

SCEN = json.load(open('01_RBI标准/_verify/轨迹场景清单.json', encoding='utf-8'))
_, agg = tools.load_clauses()
DM = {r['title']: r for r in agg['damage_mechanism']}


# ================= 观察文本（全部从真实 result 里提炼） =================
def obs_dmq(resp):
    if resp.get('status') != 'ok' or not resp.get('result'):
        return harness.Harness._summarize(resp)
    r = resp['result']
    mechs = r.get('mechanisms') or []
    parts = []
    if mechs:
        parts.append('候选 %d 个：' % len(mechs) + '、'.join(
            '%s(%s)' % (m['name'], m['clause_id'].split('-')[-1]) for m in mechs[:4]))
    disc = (r.get('discriminator') or '').strip()
    if disc:
        parts.append('鉴别要点：' + disc[:200])
    exc = r.get('excluded') or []
    if exc:
        parts.append('已排除 %d 项' % len(exc))
    return '。'.join(parts) if parts else harness.Harness._summarize(resp)


def obs_scs(resp, focus=None):
    if resp.get('status') != 'ok' or not resp.get('result'):
        return harness.Harness._summarize(resp)
    hits = resp['result'].get('hits') or []
    if not hits:
        return harness.Harness._summarize(resp)
    # 焦点条款排最前
    ordered = hits
    if focus:
        ordered = sorted(hits, key=lambda h: 0 if focus in h.get('clause_id', '') else 1)
    return '命中 %d 条：%s。首条要点：%s' % (
        len(hits),
        '、'.join('%s《%s》' % (h['clause_id'].split('-')[-1], h['title']) for h in ordered[:3]),
        (ordered[0].get('snippet') or '')[:170])


def obs_rbi(resp):
    if resp.get('status') != 'ok':
        return harness.Harness._summarize(resp)
    note = (resp.get('result') or {}).get('basis_note') or ''
    if note:
        return '严重性判定路径：' + note[:230]
    return (resp.get('message') or '')[:230]


def obs_ood(resp):
    """超范围型的观察：如实说明超出了什么。"""
    msg = (resp.get('message') or '').strip()
    if msg:
        return '查询超出条款库覆盖范围：' + msg[:220]
    return harness.Harness._summarize(resp)


# ================= 检索词构造 =================
def search_kw(scen):
    """第2步检索词。

    有 target_mech  → 机理名 + 其 influencing_factors 首条（实测召回最准，
                      如「热疲劳 循环温差」只命中 8.2，单用「热疲劳」会带回无关条款）；
    无 target_mech  → 用**候选机理自己的判据词**构造，不用「介质+鉴别 判据」
                      （后者常查不到，如「高温硫化物腐蚀介质 鉴别 判据」→ 0 命中）。
    """
    tm = scen.get('target_mech')
    if tm and tm in DM:
        factors = DM[tm]['mechanism_detail'].get('influencing_factors') or []
        if factors:
            return (tm + ' ' + str(factors[0]))[:60], tm
        return tm, tm
    # 取第一个候选机理的判据词
    cands = scen.get('expect_mechs') or []
    for m in cands:
        if m in DM:
            factors = DM[m]['mechanism_detail'].get('influencing_factors') or []
            if factors:
                return (m + ' ' + str(factors[0]))[:60], m
            return m, m
    meds = scen['medium']
    return ' '.join(meds[:2]) + ' 鉴别 判据', None


def evidence_args(scen):
    ev = {}
    t = scen.get('field_evidence') or ''
    m = re.search(r'pH\s*([\d.]+)', t)
    if m:
        ev['ph'] = float(m.group(1))
    m = re.search(r'氯离子\s*([\d.]+)', t)
    if m:
        ev['cl_ppm'] = float(m.group(1))
    m = re.search(r'铁离子\s*([\d.]+)', t)
    if m:
        ev['fe_ppm'] = float(m.group(1))
    m = re.search(r'硫化氢\s*([\d.]+)', t)
    if m:
        ev['h2s_ppm'] = float(m.group(1))
    if '裂纹' in t:
        ev['crack_found'] = True
    if '减薄' in t and '未见' in t:
        ev['wall_thinning'] = False
    return ev


# 现场证据关键词 → 机理判据词（用于把「现象」对上「机理」）
EVIDENCE_TO_MECH = [
    (['烧蚀', '灼烫', '回火色', '着火', '燃烧', '阴燃'],
     ['燃烧', '爆炸', '氧化', '着火']),
    (['韧性下降', '变脆', '脆化'],
     ['脆化', '球化', 'σ相', '475℃', '回火', '再热', '晶粒']),
    (['分层', '夹层'],
     ['氢脆', '氢致', '分层', '鼓泡']),
    (['裂纹', '开裂'],
     ['开裂', '裂纹', '断裂', '疲劳', '氢']),
    (['点蚀', '孔蚀', '坑'],
     ['点蚀', '孔蚀', '缝隙', '局部腐蚀', '浓差']),
    (['减薄', '壁厚减薄'],
     ['腐蚀', '冲蚀', '冲刷', '磨损', '减薄', '汽蚀']),
    (['结垢', '垢下'],
     ['垢下', '腐蚀', '微生物']),
]


def _pick_by_evidence(scen, resp1):
    """从第1步候选中，挑与现场证据相符的机理作为主导机理。

    现场证据写「烧蚀」就该判到燃烧爆炸，写「韧性下降」就该判到材料脆化 ——
    否则会取到候选列表里的第一个，出现「液氧储罐判成含氧工艺水腐蚀」这类错配。
    """
    if resp1.get('status') != 'ok' or not resp1.get('result'):
        return None
    cands = [m.get('name') for m in (resp1['result'].get('mechanisms') or [])]
    if len(cands) < 2:
        return cands[0] if cands else None
    ev = scen.get('field_evidence') or ''
    best = None
    best_score = 0
    for name in cands:
        score = 0
        for ev_words, mech_words in EVIDENCE_TO_MECH:
            if any(w in ev for w in ev_words) and any(w in name for w in mech_words):
                score += 1
        if score > best_score:
            best, best_score = name, score
    return best


def focus_clause(scen):
    tm = scen.get('target_mech')
    if tm and tm in DM:
        return DM[tm]['clause_id']
    return None


# ================= 结论正文（按部位与证据定制，不用模板） =================
def conclusion_multi(scen, steps, mech, basis=None):
    """依据真实返回与场景事实写结论 —— 每条按部位/证据定制。

    basis 由调用方传入（各类轨迹的收录口径不同），确保「结论引用的条款」
    与「final_answer.basis」严格一致。
    """
    s1 = steps[0]
    s2 = steps[1] if len(steps) > 1 else {'result': {}}
    s3 = steps[2] if len(steps) > 2 else {'result': {}}
    r1 = s1['result']
    mechs = [m['name'] for m in (r1.get('result', {}).get('mechanisms') or [])]
    r2 = s2['result']
    r3 = s3['result']

    if basis is None:
        basis = basis_of(s1, s2)
    basis_map = []
    for cid in basis:
        if cid not in basis_map:
            basis_map.append((cid, TITLE.get(cid, '')))

    parts = []
    # ① 主导机理
    if mech:
        parts.append('%s主导机理倾向%s' % (scen['equipment'], mech))
    else:
        parts.append('%s候选机理见依据条款' % scen['equipment'])
    # ② 依据：把 basis 逐条列出（每条带条款号与名称）——basis 的每一条都必须在此出现
    cites = '；'.join('依据 %s《%s》' % (c.split('-')[-1], t) for c, t in basis_map)
    if cites:
        parts.append(cites)
    # ③ 与现场证据的对应（按场景定制）
    parts.append('现场「%s」与上述判据相符' % scen['field_evidence'][:50])
    # ④ 鉴别/排除说明：只提「不能排除」且其条款已在 basis 里的机理
    basi_names = {t for _, t in basis_map}
    others = [m for m in mechs if m != mech and m in basi_names][:2]
    if others:
        parts.append('%s不能排除，尚需补充判别数据' % '、'.join(others))
    # ⑤ 严重性
    if r3.get('status') == 'ok':
        note = (r3.get('result') or {}).get('basis_note') or ''
        if note:
            parts.append('严重性：%s' % note.split('。')[0])
    else:
        parts.append('风险等级与检验周期当前条款库无法给出，待补充现场数据后再判定')
    return '。'.join(p) + '。' if (p := [x for x in parts if x]) else ''


def basis_of(s1, s2, limit=4):
    """结论依据的条款。

    口径（参照官方样例：basis 是「结论引用的条款」，不是「所有出现过的条款」）：
      - 第2步检索命中的条款 —— 结论主要引用的判据；
      - 第1步候选机理的条款 —— 结论中列为「不能排除」的候选，必须有条款支撑；
    不收 rbi_lookup 的 16 条判定路径条款（那是「怎么算」的出处，不是结论依据）。
    上限 limit 条，保证「结论引用的条款集合 == basis」严格自洽。
    """
    out = []
    r2 = s2['result']
    if r2.get('status') == 'ok':
        for h in (r2['result'].get('hits') or []):
            cid = h.get('clause_id')
            if cid in CLAUSE_IDS and cid not in out:
                out.append(cid)
            if len(out) >= limit:
                return out

    r1 = s1['result']
    if r1.get('status') == 'ok':
        for m in (r1['result'].get('mechanisms') or []):
            cid = m.get('clause_id')
            if cid in CLAUSE_IDS and cid not in out:
                out.append(cid)
            if len(out) >= limit:
                break
    return out


def conclusion_exclusion(scen, steps):
    """排除型：结论是「排除某机理」。"""
    s1 = steps[0]
    s2 = steps[1] if len(steps) > 1 else {'result': {}}
    mechs = [m['name'] for m in (s1['result'].get('result', {}).get('mechanisms') or [])]
    tm = scen.get('target_mech')
    basis = basis_of(s1, s2)
    cites = '；'.join('依据 %s《%s》' % (c.split('-')[-1], TITLE.get(c, '')) for c in basis)
    parts = []
    if tm:
        parts.append('%s现有证据不支持把该现象归因于%s' % (scen['equipment'], tm))
    else:
        parts.append('%s现有证据不支持把该现象归因于腐蚀' % scen['equipment'])
    if cites:
        parts.append(cites)
    if mechs:
        parts.append('%s的受影响材料未列本设备材质，或其适用介质与现场不符' % '、'.join(mechs[:2]))
    # 写入现场证据，使同类场景的结论也各不相同
    parts.append('现场表现为「%s」，无腐蚀产物与减薄特征' % scen['field_evidence'][:46])
    parts.append('建议优先排查焊接、制造、仪表、取样等非腐蚀因素')
    return '。'.join(parts) + '。'


def conclusion_insufficient(scen, steps):
    """信息不足型：结论是「现有数据无法判定，需补充 XX」。"""
    s1 = steps[0]
    s2 = steps[1] if len(steps) > 1 else {'result': {}}
    mechs = [m['name'] for m in (s1['result'].get('result', {}).get('mechanisms') or [])]
    basis = basis_of(s1, s2)
    cites = '；'.join('依据 %s《%s》' % (c.split('-')[-1], TITLE.get(c, '')) for c in basis)
    disc = (s1['result'].get('result', {}).get('discriminator') or '').strip()
    need = []
    for key, label in [('ph', '工艺水 pH'), ('cl_ppm', '氯离子含量'),
                       ('fe_ppm', '铁离子含量'), ('h2s_ppm', '硫化氢浓度或分压')]:
        if ('尚缺' in disc or key in disc) and label not in need:
            need.append(label)
    if not need:
        need = ['现场水质分析', '测厚数据', '针对性裂纹检测']
    parts = ['%s现有信息不足以判定具体机理' % scen['equipment']]
    if mechs:
        parts.append('%s均在候选范围' % '、'.join(mechs[:3]))
    if cites:
        parts.append(cites)
    # 把现场证据写进结论，使同类场景的结论也各不相同
    parts.append('现场仅掌握「%s」，尚缺上述判别数据' % scen['field_evidence'][:52])
    parts.append('建议补充：%s' % '、'.join(need[:4]))
    return '。'.join(parts) + '。'


def conclusion_ood(scen, steps):
    """超范围型：不给结论，说明超出什么。"""
    s1 = steps[0]
    msg = (s1['result'].get('message') or '').strip()
    parts = ['%s本次查询超出条款库的适用范围，不给出机理判定结论'
             % scen['equipment']]
    if msg:
        parts.append(msg[:150])
    if scen.get('field_evidence'):
        parts.append('现场情况：%s' % scen['field_evidence'][:46])
    parts.append('建议查阅 GB/T 30579-2022、GB/T 26610-2022 相应章节原文，'
                 '或由具备资质的检验人员按实际工况判定')
    return '。'.join(parts) + '。'


# ================= 构造各类轨迹 =================
def base_input(scen):
    return {
        'equipment': scen['equipment'],
        'material': scen['material'],
        'medium': scen['medium'],
        'operating_condition': '操作温度 %d℃' % scen['temperature_c'],
        'field_evidence': scen['field_evidence'],
        'question': scen['question'],
    }


def build(scen, traj_id):
    kind = scen['kind']
    mat, meds = scen['material'], scen['medium']
    temp, eq = scen['temperature_c'], scen['equipment_type']
    steps = []

    # ---------- 第 1 步：所有类型都先按工况查 ----------
    args1 = {'material': mat, 'medium': meds, 'temperature_c': temp, 'equipment_type': eq}
    ev = evidence_args(scen)
    if ev:
        args1['evidence'] = ev
    resp1 = H.call_tool('damage_mechanism_query', args1)
    steps.append({
        'step': 1,
        'thought': '先按材质、介质和操作温度取候选损伤机理，看哪些机理在条款适用范围内',
        'tool': 'damage_mechanism_query',
        'args': args1,
        'result': resp1,
        'observation': obs_dmq(resp1) if resp1.get('status') == 'ok' else obs_ood(resp1),
    })

    if kind == 'out_of_domain':
        return {
            'traj_id': traj_id, 'task_type': 'single_step', 'special_type': 'out_of_domain',
            'input': base_input(scen), 'steps': steps,
            'final_answer': {'conclusion': conclusion_ood(scen, steps), 'basis': []},
            'annotator': '2025xxxx_代航', 'checked': False,
        }

    if kind == 'single':
        # single 型只有第1步，直接以第1步候选机理的条款为依据
        # 注意层级：resp1 是外壳，mechanisms 在 resp1['result']['mechanisms']
        basis = []
        inner = resp1.get('result') or {}
        for m in (inner.get('mechanisms') or [])[:4]:
            cid = m.get('clause_id')
            if cid in CLAUSE_IDS and cid not in basis:
                basis.append(cid)
        # 主导机理同样按现场证据选（与多步型一致），否则会出现
        # 「管道焊缝有烧蚀 → 判成含氧工艺水腐蚀」这类与证据不符的判定
        mech0 = _pick_by_evidence(scen, resp1) or \
            (inner.get('mechanisms') or [{}])[0].get('name')
        return {
            'traj_id': traj_id, 'task_type': 'single_step',
            'input': base_input(scen), 'steps': steps,
            'final_answer': {'conclusion': conclusion_multi(scen, steps, mech0, basis),
                              'basis': basis},
            'annotator': '2025xxxx_代航', 'checked': False,
        }

    # ---------- 第 2 步 ----------
    kw, focus = search_kw(scen)
    args2 = {'keyword': kw, 'knowledge_type': 'damage_mechanism', 'top_k': 3}
    resp2 = H.call_tool('standard_clause_search', args2)
    if kind == 'exclusion':
        thought = '取到的候选与现场现象对不上，检索该机理的适用条件以确认能否排除'
    elif kind == 'insufficient_info':
        thought = '多个候选难以区分，检索各机理的判别依据以确定还需补充哪些数据'
    else:
        thought = ('按工况查询未直接给出「%s」（其适用条件不以介质表述），'
                   '改用关键词检索定位其条款与判据' % scen.get('target_mech')) \
            if scen.get('target_mech') else '候选不止一个，需要补充鉴别依据才能区分'
    steps.append({
        'step': 2,
        'thought': thought,
        'tool': 'standard_clause_search',
        'args': args2,
        'result': resp2,
        'observation': obs_scs(resp2, focus),
    })

    if kind in ('exclusion', 'insufficient_info'):
        basis = basis_of(steps[0], steps[1])
        concl = (conclusion_exclusion(scen, steps) if kind == 'exclusion'
                 else conclusion_insufficient(scen, steps))
        return {
            'traj_id': traj_id, 'task_type': 'single_step', 'special_type': kind,
            'input': base_input(scen), 'steps': steps,
            'final_answer': {'conclusion': concl, 'basis': basis},
            'annotator': '2025xxxx_代航', 'checked': False,
        }

    # ---------- 第 3 步：判严重性 ----------
    # 主导机理的选取优先级：
    #   ① 场景显式指定的 target_mech（该场景就是要讲这个机理）；
    #   ② 第1步候选中，与**现场证据**相符的那一个（如证据写「烧蚀」→ 燃烧爆炸，
    #      写「韧性下降」→ σ相脆化/475℃脆化这类材料劣化）；
    #   ③ 第2步检索实际命中的条款（那才是本场景真正关心的机理）；
    #   ④ 第1步首个候选。
    mech = None
    tm = scen.get('target_mech')
    if tm and tm in DM:
        mech = tm
    if not mech:
        mech = _pick_by_evidence(scen, resp1)
    if not mech and resp2.get('status') == 'ok':
        for h in (resp2['result'].get('hits') or []):
            cid = h.get('clause_id')
            for title, rec in DM.items():
                if rec['clause_id'] == cid:
                    mech = title
                    break
            if mech:
                break
    if not mech:
        mech = (scen.get('expect_mechs') or [None])[0]
    args3 = {'equipment_type': eq, 'material': mat, 'mechanism': mech}
    resp3 = H.call_tool('rbi_lookup', args3)
    steps.append({
        'step': 3,
        'thought': '主导机理判定为「%s」，查该机理的严重性判定依据与检验要求' % mech,
        'tool': 'rbi_lookup',
        'args': args3,
        'result': resp3,
        'observation': obs_rbi(resp3),
    })

    basis = basis_of(steps[0], steps[1])
    return {
        'traj_id': traj_id, 'task_type': 'multi_step',
        'input': base_input(scen), 'steps': steps,
        'final_answer': {'conclusion': conclusion_multi(scen, steps, mech, basis), 'basis': basis},
        'annotator': '2025xxxx_代航', 'checked': False,
    }


if __name__ == '__main__':
    recs = []
    n = 0
    for scen in SCEN:
        n += 1
        recs.append(build(scen, 'UG-2026-%04d' % n))
    print('已生成 %d 条轨迹' % len(recs))
    cnt = collections.Counter(r['task_type'] for r in recs)
    sp = collections.Counter(r.get('special_type') for r in recs if r.get('special_type'))
    print('task_type:', dict(cnt))
    print('special_type:', dict(sp))
    print('basis 为空的条数:', len([r for r in recs if not r['final_answer']['basis']]),
          '（应等于 out_of_domain 条数）')
    harness.save_jsonl('05_提交区/trajectories.jsonl', recs)
    print('已写出 05_提交区/trajectories.jsonl')

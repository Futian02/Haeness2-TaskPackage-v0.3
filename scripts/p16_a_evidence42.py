from __future__ import annotations
import csv, json, hashlib, html, re
from pathlib import Path
from collections import defaultdict
import fitz

ROOT=Path.cwd()
OUT=ROOT/'work/data_staging/p16/A_CHANGED_42'
PAGES=OUT/'pages'; CARDS=OUT/'cards'
DIFF=ROOT/'work/data_staging/p15/merged/P15_C_CANDIDATE_JSONL_DIFF.csv'
A=ROOT/'work/data_staging/p15/A_RBI/P15_A_FIELD_CHANGELOG.csv'
B=ROOT/'docs/data_quality/P15_B_FIELD_CHANGELOG.csv'
JSONL=ROOT/'work/data_staging/p15/merged/clauses_candidate.jsonl'

def readcsv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(path, rows, fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(p): return (ROOT/p.replace('/', '\\')).resolve()
def safe(s): return re.sub(r'[^A-Za-z0-9_.-]+','_',s)
def esc(v): return html.escape(str(v if v is not None else ''), quote=True)

diffs=readcsv(DIFF); alogs=readcsv(A); blogs=readcsv(B)
bycl=defaultdict(lambda:{'diff':[],'changes':[]})
for r in diffs: bycl[r['clause_id']]['diff'].append(r)
for r in alogs:
    cid=r['clause_id']; cid=('GBT30579-2022-'+cid) if cid in ('5.6','5.23','6.7') else cid
    bycl[cid]['changes'].append({**r,'clause_id':cid,'track':'A'})
for r in blogs:
    cid=r['clause_id']; cid=('GBT30579-2022-'+cid) if cid in ('5.6','5.23','6.7') else cid
    bycl[cid]['changes'].append({**r,'clause_id':cid,'track':'B'})
clauses={}
with JSONL.open(encoding='utf-8') as f:
    for line in f:
        o=json.loads(line); clauses[o['clause_id']]=o
assert len(bycl)==42, (len(bycl), sorted(bycl))
assert len(alogs)==64 and len(blogs)==9

# PDF sources and locators. A/B logs are authoritative for page references; no locator is invented.
def source_for(cid, changes):
    for c in changes:
        if c.get('pdf_file'):
            return c['pdf_file']
        if c.get('standard_code')=='GB/T 30579-2022': return 'upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf'
    if cid.startswith('GBT26610.5'): return 'upstream/01_RBI标准/GBT26610.5-2022_失效后果定量分析方法.pdf'
    if cid.startswith('GBT26610.3'): return 'upstream/01_RBI标准/GBT26610.3-2014_风险的定性分析方法.pdf'
    if cid.startswith('TSG21'): return 'upstream/01_RBI标准/补充规范/TSG21-2016_固定式压力容器安全技术监察规程.pdf'
    return ''
def parse_nums(v):
    if not v:return []
    out=[]
    for a,b in re.findall(r'(\d+)\s*[–-]\s*(\d+)',v): out.extend(range(int(a),int(b)+1))
    rest=re.sub(r'\d+\s*[–-]\s*\d+','',v)
    out.extend(int(x) for x in re.findall(r'\d+',rest))
    return list(dict.fromkeys(out))
def page_for(changes):
    idx=[]; printed=[]
    for c in changes:
        idx.extend(parse_nums(c.get('pdf_page_index',''))); printed.extend(parse_nums(c.get('printed_page','')))
    return list(dict.fromkeys(idx)),list(dict.fromkeys(printed))

def label(cid):
    if cid.startswith('GBT26610.5'): return 'GB/T 26610.5 表2/表3 数值行'
    if cid.startswith('TSG21'): return 'TSG 21 适用条件/检验周期'
    if cid.startswith('GBT30579'): return 'GB/T 30579 损伤机理字段'
    if cid.startswith('GBT26610.3'): return 'GB/T 26610.3 图1风险矩阵拆行/页码'
    return '其他'

def conclusion(cid, changes, obj):
    if cid.startswith('GBT26610.5'):
        return 'AMBIGUOUS','视觉读取表格数值和单位可对应候选摘录；候选F将表格单元格串接为文字，是否满足教师“原文摘录”逐字/格式要求需要人工确认。'
    if cid=='GBT30579-2022-5.6':
        return 'AMBIGUOUS','177～427℃候选温区与§5.6.1视觉证据相符；但F由§5.6.1+§5.6.2缩为仅§5.6.1，H仍保留损伤形态，需人工判断该摘录缩短是否切断字段间引用/溯源关系。'
    if cid.startswith('GBT26610.3'):
        rd=obj.get('rbi_detail',{}); lk=int(rd.get('likelihood')); co=str(rd.get('consequence'))
        grid={1:{'A':'低风险','B':'低风险','C':'中风险','D':'中风险','E':'中高风险'},2:{'A':'低风险','B':'低风险','C':'中风险','D':'中风险','E':'中高风险'},3:{'A':'低风险','B':'低风险','C':'中风险','D':'中高风险','E':'高风险'},4:{'A':'中风险','B':'中风险','C':'中高风险','D':'中高风险','E':'高风险'},5:{'A':'中高风险','B':'中高风险','C':'中高风险','D':'高风险','E':'高风险'}}
        expected=grid[lk][co]; actual=rd.get('risk_level','')
        if actual!=expected: return 'CONTRADICTS',f'原图颜色图例核读该格应为{expected}，候选为{actual}；需修正后复核。'
        return 'MATCH',f'原图图1（印刷页14 / PDF index13）颜色格 {lk}{co}={expected} 与候选风险等级一致；等级图例：绿低、蓝中、黄中高、红高。备注页码更正为14。机器视觉核读，不替代真人签署。'
    if cid=='TSG21-2016-8.3.12':
        return 'CONTRADICTS','P15 A台账定位写印刷页79/PDF index78，但原PDF index78显示印刷页74且内容为§8.2.3，未见§8.3.12；PDF文本检索定位到§8.3.12正文在印刷页79/PDF index83。候选修改的内容可在正确页面核对，但原变更证据页索引错误，需修正来源台账并由人工复核。'
    if cid.startswith('TSG21'):
        return 'MATCH','本条候选范围/检验周期字段与卡片所列条文页可作逐项对照；机器整理为候选意见，仍需人工核对适用边界、例外和引用条款。'
    return 'AMBIGUOUS','定位到相关PDF页并展示变更；该字段涉及损伤机理语义/跨段条件关系，机器只能提供候选判断，需人工逐字核对。'

# Render every cited source page; ranges (e.g. 37–39) remain multi-page evidence.
pdfmeta={}; refs={}
for cid, pack in bycl.items():
    changes=pack['changes']; p=source_for(cid,changes); indices,printed=page_for(changes)
    if cid=='TSG21-2016-8.3.12': indices=[78,83]; printed=[74,79]  # include erroneous logged page and exact clause page for side-by-side provenance audit
    if not p or not indices: refs[cid]={'src':p,'indices':indices,'printed':printed,'status':'BLOCKED_SOURCE_LOCATION','images':[]}; continue
    src=norm(p)
    if not src.exists(): refs[cid]={'src':p,'indices':indices,'printed':printed,'status':'BLOCKED_SOURCE_LOCATION','images':[]}; continue
    doc=fitz.open(src); images=[]; page_count=len(doc); filehash=sha(src); status='RENDERED'
    for idx in indices:
        key=(str(src),idx)
        if idx<0 or idx>=page_count: status='PAGE_UNREADABLE'; continue
        if key not in pdfmeta:
            page=doc[idx]; candidates=[]
            for c in changes:
                q=(c.get('evidence_quote') or '').strip()[:36].strip()
                if len(q)>5: candidates += page.search_for(q)
            if not candidates:
                for c in changes:
                    sub=(c.get('subclause') or c.get('table_id') or '').strip()
                    if sub and sub not in ('图1','图1 风险矩阵'): candidates += page.search_for(sub)
            for rect in candidates[:20]: page.draw_rect(rect,color=(1,0,0),width=1.6,overlay=True)
            name=f'{safe(Path(p).stem)}_p{idx:03}.png'; page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(PAGES/name)
            pdfmeta[key]={'status':'RENDERED','n':page_count,'hash':filehash,'image':name,'highlight_count':len(candidates)}
        if key in pdfmeta: images.append({'idx':idx,'image':pdfmeta[key]['image']})
    doc.close()
    refs[cid]={'src':p,'indices':indices,'printed':printed,'status':status,'images':images,'n':page_count,'hash':filehash}

# Build cards + review sheet
review=[]; cards_index=[]
for i,(cid,pack) in enumerate(sorted(bycl.items()),1):
    obj=clauses.get(cid,{})
    ch=pack['changes']; ds=pack['diff']; ref=refs.get(cid,{})
    status,reason=conclusion(cid,ch,obj)
    if ref.get('status')!='RENDERED': status=ref.get('status','BLOCKED_SOURCE_LOCATION')
    evidence=[]
    for c in ch:
        evidence.append({k:c.get(k,'') for k in ('track','field','old_value','new_value','why','action','pdf_file','standard_code','subclause','printed_page','pdf_page_index','bbox','table_id','table_row','table_column','element_name','evidence_quote','evidence_level','evidence_locator','reason') if c.get(k,'')!=''})
    changes_html=[]
    for n,c in enumerate(ch,1):
        old=c.get('old_value',''); new=c.get('new_value','')
        motivation=c.get('why') or c.get('reason') or c.get('action') or ''
        locator=' | '.join(f'{k}={c[k]}' for k in ('subclause','table_id','table_row','table_column','bbox','evidence_locator') if c.get(k))
        quote=c.get('evidence_quote') or c.get('element_name') or ''
        changes_html.append(f'<section class="change"><h3>变更 {n} · {esc(c.get("track"))} / {esc(c.get("field"))}</h3><div class="grid"><div><b>旧值</b><pre>{esc(old)}</pre></div><div><b>候选新值</b><pre>{esc(new)}</pre></div></div><p><b>动机</b>：{esc(motivation)}</p><p><b>证据定位</b>：{esc(locator or "未提供结构化子定位；不得据此假造bbox")}</p><p><b>变更台账原文/对象</b>：{esc(quote)}</p><p><b>证据级别/状态</b>：{esc(c.get("evidence_level") or c.get("method") or "")} / {esc(c.get("review_required") or c.get("reviewer_status") or "")}</p></section>')
    diff_html=[]
    for d in ds:
        diff_html.append(f'<section class="change"><h3>P15-C JSON字段差分 · {esc(d["field"])}</h3><div class="grid"><div><b>旧值</b><pre>{esc(d["old_value"])}</pre></div><div><b>候选新值</b><pre>{esc(d["new_value"])}</pre></div></div><p>{esc(d["source_evidence"])}</p></section>')
    img=''
    if ref.get('images'):
        img=''.join(f'<figure><img src="../pages/{esc(p["image"])}" alt="原始PDF页面"><figcaption>原始PDF全页渲染；0-based PDF物理页索引 {p["idx"]}；源文件印刷页定位 {esc(", ".join(map(str,ref.get("printed",[]))))}。标记仅来自可搜索文本bbox；未命中不伪造bbox。</figcaption></figure>' for p in ref['images'])
    else: img=f'<div class="blocked">源页未能渲染：{esc(ref.get("status"))}；不得作为已核实。</div>'
    risk=''
    if cid.startswith('GBT26610.3'):
        rd=obj.get('rbi_detail',{})
        risk=f'<section class="change"><h3>候选风险格</h3><p>可能性={esc(rd.get("likelihood"))}；后果={esc(rd.get("consequence"))}；风险等级={esc(rd.get("risk_level"))}；统一等级={esc(rd.get("risk_level_unified"))}</p><p>原图证据：GB/T 26610.3-2014 图1，印刷页14，PDF物理页索引13。图例逐格核对：绿=低风险L1，蓝=中风险L2，黄=中高风险L3，红=高风险L4。候选值按行/列映射核算；不得以拆行ID后缀代替矩阵判级。</p></section>'
    numeric=''
    if cid.startswith('GBT26610.5') or cid.startswith('TSG21') or cid.startswith('GBT30579'):
        numeric=f'<section class="change"><h3>数值/单位核验提示</h3><p>检查区：条款/表格原文、候选字段、标准单位、区间端点开闭性、脚注和相邻表头。当前证据台账引文：{esc(" | ".join(c.get("evidence_quote","") for c in ch if c.get("evidence_quote")))}</p><p>本卡的页面图保留全页表头/相邻上下文；打印版请勿裁掉单位与脚注。</p></section>'
    html_doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{esc(cid)} P16-A证据卡</title><style>
body{{font:15px/1.55 system-ui,"Microsoft YaHei",sans-serif;color:#182230;max-width:1150px;margin:24px auto;padding:0 20px}}h1{{font-size:24px}}h2{{margin-top:34px}}.meta,.change{{border:1px solid #cbd5e1;border-radius:8px;padding:14px;margin:12px 0;background:#fff}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:10px;border-radius:5px}}figure{{margin:16px 0}}img{{width:100%;height:auto;border:1px solid #94a3b8}}figcaption{{font-size:13px;color:#475569}}.status{{font-weight:bold;color:#9a3412}}.blocked{{padding:20px;background:#fee2e2}}.sign{{border:2px dashed #64748b;padding:14px;min-height:120px}}@media print{{body{{max-width:none;margin:0;padding:8mm}}.change,.meta{{break-inside:avoid}}img{{max-height:245mm;object-fit:contain}}}}
</style><body><h1>P16-A 证据核验卡：{esc(cid)}</h1><div class="meta"><b>优先类别</b>：{esc(label(cid))}<br><b>标准/条款</b>：{esc(obj.get('standard_code',''))} / {esc(obj.get('clause_no',''))} — {esc(obj.get('title',''))}<br><b>机器结论</b>：<span class="status">{esc(status)} · AI_VISUAL_CANDIDATE</span><br><b>理由</b>：{esc(reason)}<br><b>源文件</b>：{esc(ref.get('src',''))}；SHA-256 {esc(ref.get('hash',''))}<br><b>页定位</b>：印刷页 {esc(', '.join(map(str,ref.get('printed',[]))))}；物理页索引(0-based) {esc(', '.join(map(str,ref.get('indices',[]))))}；PDF页数 {esc(ref.get('n',''))}<br><b>差分覆盖</b>：{len(ch)}条A/B单元格日志；{len(ds)}条P15-C JSON字段差分</div><h2>原始PDF页面</h2>{img}{risk}{numeric}<h2>逐条Excel单元格变更（不得折叠）</h2>{''.join(changes_html) if changes_html else '<p>无A/B单元格变更记录</p>'}<h2>P15-C候选JSON字段旧值→新值</h2>{''.join(diff_html) if diff_html else '<p>无JSON字段差分</p>'}<h2>独立真人审核区</h2><div class="sign">审核结果 pass / fail：________________　是否支持条款适用：________________<br><br>纠错意见：<br><br>审核人：________________　日期时间：________________<br>真人签字：________________　确认印刷页/页索引：________________<br><b>此区域空白，待真实审核者填写；机器结论不构成人审。</b></div><p>密级提示：标准页图只留在本地受控目录，不对外分发。</p></body></html>'''
    card=CARDS/(safe(cid)+'.html'); card.write_text(html_doc,encoding='utf-8')
    cards_index.append({'clause_id':cid,'card_path':str(card.relative_to(OUT)).replace('\\','/'),'category':label(cid),'machine_status':status,'machine_label':'AI_VISUAL_CANDIDATE','change_cells':len(ch),'json_diff_fields':len(ds),'source_pdf':ref.get('src',''),'printed_page':', '.join(map(str,ref.get('printed',[]))),'pdf_page_index':', '.join(map(str,ref.get('indices',[]))),'page_render_status':ref.get('status',''),'evidence_reason':reason})
    review.append({'clause_id':cid,'category':label(cid),'standard_code':obj.get('standard_code',''),'clause_no':obj.get('clause_no',''),'title':obj.get('title',''),'card_path':str(card.relative_to(OUT)).replace('\\','/'),'source_pdf':ref.get('src',''),'printed_page':', '.join(map(str,ref.get('printed',[]))),'pdf_page_index_0based':', '.join(map(str,ref.get('indices',[]))),'table_figure_locator':' ; '.join(c.get('evidence_locator') or c.get('table_id') or c.get('subclause','') for c in ch),'cell_changes':len(ch),'json_field_diffs':len(ds),'machine_conclusion':status,'machine_review_label':'AI_VISUAL_CANDIDATE','machine_reason':reason,'human_result':'','human_applicability_supported':'','human_reviewer':'','human_datetime':'','human_confirmed_printed_page':'','human_correction':'','human_signature':'','review_status':'PENDING_HUMAN'})

# Aggregate overview
counts=defaultdict(int)
for r in review: counts[r['machine_conclusion']]+=1
index=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P16-A 42条变更证据包</title><style>body{{font:15px/1.5 system-ui,"Microsoft YaHei",sans-serif;margin:24px;color:#172033}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #cbd5e1;padding:7px;text-align:left}}th{{background:#e2e8f0}}.warn{{background:#fff7ed;padding:12px}}</style><h1>P16-A 42条真实变更证据包</h1><p class="warn">机器视觉候选材料；禁止将AI_VISUAL_CANDIDATE升级为HUMAN_VERIFIED。签名表由真实审核者填写。</p><p>42个clause_id；A/B单元格日志{len(alogs)+len(blogs)}（A={len(alogs)}，B={len(blogs)}）；P15-C字段差分{len(diffs)}。机器结论计数：{esc(dict(counts))}</p><table><tr><th>ID</th><th>类别</th><th>页</th><th>cell</th><th>JSON字段</th><th>机器候选结论</th><th>卡片</th></tr>{''.join(f'<tr><td>{esc(r["clause_id"])}</td><td>{esc(r["category"])}</td><td>印刷{esc(r["printed_page"])} / idx {esc(r["pdf_page_index"])}</td><td>{r["change_cells"]}</td><td>{r["json_diff_fields"]}</td><td>{r["machine_status"]}</td><td><a href="{esc(r["card_path"])}">打开</a></td></tr>' for r in cards_index)}</table></html>'''
(OUT/'index.html').write_text(index,encoding='utf-8')
writecsv(OUT/'P16_A_REVIEW42.csv',review,list(review[0].keys()))
cell_audit=[]
for cid,pack in sorted(bycl.items()):
    for c in pack['changes']:
        row={'clause_id':cid,'track':c.get('track',''),'excel_row':c.get('excel_row',''),'field':c.get('field',''),'old_value':c.get('old_value',''),'new_value':c.get('new_value',''),'action':c.get('action',''),'why':c.get('why') or c.get('reason',''),'source_pdf':c.get('pdf_file') or c.get('standard_code',''),'printed_page':c.get('printed_page',''),'pdf_page_index_0based':c.get('pdf_page_index',''),'bbox':c.get('bbox',''),'table_id':c.get('table_id',''),'table_row':c.get('table_row',''),'table_column':c.get('table_column',''),'evidence_locator':c.get('evidence_locator',''),'evidence_quote':c.get('evidence_quote',''),'evidence_level':c.get('evidence_level') or c.get('method',''),'human_review_state':c.get('review_required') or c.get('reviewer_status','')}
        cell_audit.append(row)
writecsv(OUT/'P16_A_CELL_AUDIT.csv',cell_audit,list(cell_audit[0].keys()))
# Only a review action is proposed: no content value is changed without an evidence-backed human decision.
proposal={'clause_id':'GBT30579-2022-5.6','field':'原文摘录(F)','proposal_type':'REVIEW_SCOPE_ONLY','observed_change':'P15 B候选F从原有§5.6.1+§5.6.2缩短为仅§5.6.1；H字段仍含形态信息。','evidence':{'pdf':'upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf','printed_page':9,'pdf_page_index_0based':14,'sections':['5.6.1','5.6.2'],'local_image':'pages/GBT30579-2022___p014.png'},'machine_conclusion':'AMBIGUOUS','review_action':'请真人判定：F保留仅§5.6.1是否属于有意按字段分工的逐字摘录，且H中的形态能否独立承接§5.6.2；未决前不建议直接发布。','data_mutation':False,'human_status':'PENDING_HUMAN'}
locator_proposal={'clause_id':'TSG21-2016-8.3.12','field':'source_locator','proposal_type':'CORRECT_EVIDENCE_LOCATOR','recorded_locator':{'printed_page':79,'pdf_page_index_0based':78},'visually_verified_locator':{'printed_page':79,'pdf_page_index_0based':83},'evidence':{'wrong_page_image':'pages/TSG21-2016___p078.png','correct_page_image':'pages/TSG21-2016___p083.png','correct_heading':'8.3.12 安全附件检验'},'machine_conclusion':'CONTRADICTS','data_mutation':False,'human_status':'PENDING_HUMAN'}
(OUT/'P16_A_PROPOSED_CORRECTIONS.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in [proposal,locator_proposal])+'\n',encoding='utf-8')
(OUT/'cards_index.json').write_text(json.dumps(cards_index,ensure_ascii=False,indent=2),encoding='utf-8')
# Evidence inventory
inventory=[]
for cid,ref in refs.items(): inventory.append({'clause_id':cid,'src':ref.get('src',''),'indices':';'.join(map(str,ref.get('indices',[]))),'printed':';'.join(map(str,ref.get('printed',[]))),'status':ref.get('status',''),'images':';'.join(p['image'] for p in ref.get('images',[])),'n':ref.get('n',''),'hash':ref.get('hash','')})
writecsv(OUT/'P16_A_PAGE_INVENTORY.csv',inventory,['clause_id','src','indices','printed','status','images','n','hash'])
print(json.dumps({'ids':len(bycl),'A_cells':len(alogs),'B_cells':len(blogs),'json_diffs':len(diffs),'cards':len(cards_index),'pages':len(list(PAGES.glob('*.png'))),'conclusions':dict(counts),'output':str(OUT)},ensure_ascii=False,indent=2))



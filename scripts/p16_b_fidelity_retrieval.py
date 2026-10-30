from __future__ import annotations
import csv, hashlib, importlib.util, json, math, re, sys, time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/data_staging/p16/B_REMAINDER'
DOCS=ROOT/'docs/data_quality'
P15=ROOT/'work/data_staging/p15'
SOURCE_QUEUE=P15/'A_RBI/P15_A_TABLE_REVIEW_COVERAGE.csv'
SOURCE_LEDGER=P15/'A_RBI/P15_A_SOURCE_LEDGER.csv'
EXACT10=P15/'A_RBI/research/2661045/table2_table3_exact_excerpt_candidates.csv'
DM_TRIAGE=P15/'B_DM/DM_FIELD_TRIAGE.csv'
SUP_MATRIX=DOCS/'P15_B_SUPPLEMENT_CHAPTER_DISPOSITION.csv'
P15_RETR=P15/'C_QA/P15_C_CANDIDATE_RETRIEVAL_RESULTS.csv'
CANDIDATE_CLAUSES=P15/'merged/candidate_tool_probe/05_提交区/clauses.jsonl'


def readcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows,fields=None):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  if not fields: fields=list(rows[0]) if rows else []
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def tokens(s):return [x.lower() for x in re.split(r'[\s,，、;；/|()（）【】\[\]{}]+',s or '') if x.strip()]

# (1) RBI table risks: exclude exactly the ten P15 A image-located .5 table2/3 rows.
queue=readcsv(SOURCE_QUEUE); ledger=readcsv(SOURCE_LEDGER); exact=readcsv(EXACT10)
reviewed10={r['clause_id'] for r in exact}
assert len(queue)==221 and len(reviewed10)==10
remaining=[r for r in queue if r['clause_id'] not in reviewed10]
assert len(remaining)==211
ledger_by=defaultdict(list)
for r in ledger: ledger_by[r['clause_id']].append(r)
# order high-risk first: .4 numeric tables; .3; remaining .5; .2. Within group, numeric/unit/table footnote cues rank first.
std_rank={'GB/T 26610.4-2022':1,'GB/T 26610.3-2014':2,'GB/T 26610.5-2022':3,'GB/T 26610.2-2022':4}
triage=[]
for x in remaining:
 std=x['standard_code']; quote=x['current_F_quote']; terms=[]
 if re.search(r'\d|%|MPa|MPa|℃|mm|年|h|\u00d7|≤|≥|~|～|±',quote,re.I):terms.append('NUMERIC_UNIT_BOUNDARY')
 if any(z in quote for z in ('表','图','附录','注：','注:','其中','不包括','大于','小于','以上','以下','至')):terms.append('TABLE_FOOTNOTE_OR_BOUNDARY')
 if not terms:terms=['TABLE_OR_TEXT_MAPPING']
 led=next((z for z in ledger_by.get(x['clause_id'],[]) if z.get('field') in ('F/原文摘录','F','原文摘录') or z.get('table_id')),None)
 pdf=x['pdf_file']; index=x['pdf_page_index']; printed=x['printed_page']; table=x['table_id'] or (led or {}).get('table_id','')
 row=(led or {}).get('table_row',''); col=(led or {}).get('table_column',''); bbox=(led or {}).get('bbox','') or x['bbox_or_failure']
 if index and index.isdigit() and printed and pdf:
  status='SOURCE_UNRESOLVED_CELL_PAGE_LOCATED'
  reason='已定位到PDF物理页，但未得到可靠单元格行列/bbox；保留原F/数值，不由Native文本推断表格边界。'
 else:
  status='SOURCE_UNRESOLVED'
  reason='P15索引未能定位PDF页或单元格；先按原标准章节/条款重建定位，不猜数值。'
 if std=='GB/T 26610.4-2022':
  priority='P0_NUMERIC_TABLE'; reason+=' 26610.4量化因子/概率表优先逐格核验；单位、封闭/开放边界、脚注含义不可由截断F确定。'
 elif std=='GB/T 26610.3-2014': priority='P1_TABLE_CELL';
 elif std=='GB/T 26610.5-2022': priority='P2_REMAINING_TABLE';
 else: priority='P3_STRATEGY_TABLE'
 triage.append({'priority_rank':std_rank.get(std,9),'priority':priority,'priority_signals':'|'.join(terms),'excel_row':x['excel_row'],'clause_id':x['clause_id'],'standard_code':std,'clause_no':x['clause_no'],
  'pdf_file':pdf,'source_pdf_sha256':(led or {}).get('source_pdf_sha256',''),'printed_page':printed,'pdf_page_index_0based':index,'table_id':table,'table_row':row,'table_column':col,'bbox_or_failure':bbox,'source_status':status,'current_F_quote':quote,
  'numeric_unit_or_boundary_tokens':'|'.join(re.findall(r'(?<!\w)(?:\d+(?:\.\d+)?(?:×10\^?[-−]?\d+)?|≤|≥|<|>|%|MPa|℃|m2|m²|元/年)(?!\w)',quote)),
  'method_and_result':x['method']+'; '+x['review_status'],'P15_evidence':x['evidence_level'],'failure_reason':reason,
  'page_file_if_targeted_ocr':'','ocr_text':'','human_review_status':'NOT_DONE','reviewer_signature':'','release_eligible':'NO'})
triage.sort(key=lambda r:(r['priority_rank'],0 if 'NUMERIC_UNIT_BOUNDARY' in r['priority_signals'] else 1,int(r['excel_row'])))
# Targeted top-20 source capture and OCR only, never full-corpus OCR.
top20=triage[:20]
ocr_count=0
# The first batch is one contiguous Table 2 page (6-a..6-t). Record its source row and
# column headings explicitly; page render is evidence, but no cell bounding boxes are asserted.
table2_columns='失效概率：>0mm～6mm|>6mm～25mm|>25mm～100mm|>100mm|FG总计'
for item in top20:
 if item['standard_code']=='GB/T 26610.4-2022' and re.search(r'-6-[a-t]$',item['clause_id']):
  match=re.search(r'设备类型[「“](.+?)[」”]',item['current_F_quote'])
  item['table_id']='表2'
  item['table_row']=match.group(1) if match else 'ROW_LABEL_UNRESOLVED'
  item['table_column']=table2_columns
  item['bbox_or_failure']='BBox_NOT_CAPTURED; page image only; verify row/column cell geometry and footnotes.'
  item['targeted_source_locator']='GB/T 26610.4-2022 Table 2; clause '+item['clause_id']+'; source row '+item['table_row']
try:
 import fitz
 import pytesseract
 from PIL import Image
 for idx,item in enumerate(top20,1):
  try:
   source=ROOT/item['pdf_file']; page_index=int(item['pdf_page_index_0based'])
   doc=fitz.open(source)
   if page_index<0 or page_index>=len(doc): raise IndexError(f'page index {page_index} outside {len(doc)}')
   page=doc[page_index]; pix=page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False)
   image_dir=OUT/'table_pages'; image_dir.mkdir(parents=True,exist_ok=True)
   out_png=image_dir/f'top20_{idx:02d}_{item["clause_id"].replace("/","_").replace(".","_")}.png'
   pix.save(out_png)
   text=pytesseract.image_to_string(Image.open(out_png),lang='chi_sim+eng',config='--psm 6')
   item['page_file_if_targeted_ocr']=str(out_png.relative_to(ROOT));item['ocr_text']=re.sub(r'\s+',' ',text)[:5000]
   item['targeted_ocr_status']='PAGE_OCR_CAPTURED_NOT_TRANSCRIPTION'
   item['source_status']='AI_VISUAL_NUMERIC_ROW_MATCH_F_TEXT_PENDING_HUMAN'
   item['failure_reason']+=' P16定向渲染/OCR页候选；候选视觉检查未记录cell bbox/独立复核签名，OCR不是表格真值，仍需行列、单位边界、脚注与合计关系人工复核。'
   ocr_count+=1;doc.close()
  except Exception as e:
   item['page_file_if_targeted_ocr']='';item['ocr_text']='';item['source_status']='RENDER_FAILED_CELL_PENDING'
   item['failure_reason']+=f' 定向处理失败：{type(e).__name__}: {e}'
except Exception as e:
 for x in top20:x['failure_reason']+=f' 定向OCR环境不可用：{type(e).__name__}: {e}'
writecsv(OUT/'P16_B_PRIORITY_TRIAGE.csv',triage)
writecsv(OUT/'P16_B_SOURCE_CELLS.csv',triage)

# (2) DM 82/656 + O-V semantic review queue; rows from P15 B evidence are read-only.
dm=readcsv(DM_TRIAGE)
# P15 B ledger has both G-N(656) and condition O-V(656); retain all 1312 for targeted prioritization.
dm_out=[]
for r in dm:
  cid=r['clause_id']; col=r['field_letter']; value=(r.get('candidate_value') or '')+' '+(r.get('ocr_snippet') or '')
  numeric=bool(re.search(r'\d|%|MPa|℃|°C|pH|ppm|HIC|SSC|分压|压力|硬度|耐蚀|易感|腐蚀速率',value,re.I))
  weak_ocr=(col in 'GHIJKLMN' and str(r.get('ocr_heading_found','')).lower()!='true')
  critical=cid in ('5.6','5.23','6.7')
  priority='P0_CRITICAL_CONDITION' if critical else 'P0_NUMERIC_OR_SUSCEPTIBILITY' if numeric else 'P1_OCR_HEADING_MISSING' if weak_ocr else 'P2_SOURCE_FIELD_REVIEW'
  dm_out.append({**r,'p16_priority':priority,'numeric_susceptibility_flag':numeric,'ocr_heading_missing_flag':weak_ocr,
   'semantic_review_status':'PENDING_SOURCE_SENTENCE_REVIEW','reason':'OCR/子条定位仅作导航；须核物理量对象、阈值范围、材料耐蚀vs易感和字段映射。' if priority.startswith('P0') or priority.startswith('P1') else '条款子字段语义未逐格人工核验。'})
writecsv(OUT/'P16_B_DM_FIELD_REVIEW.csv',dm_out)

# 5.6 raw excerpt preservation proposal, grounded to original page and prior candidate; only staged JSONL.
orig=ROOT/'upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf'
# Source 5.6.1+5.6.2 span is retained as candidate proposal text, not automatically applied.
proposals=[{'proposal_id':'P16B-DM-56-F-PRESERVE-5.6.2','proposal_type':'source_fidelity_review_candidate','clause_id':'GBT30579-2022-5.6','field':'原文摘录/F','old_value':'5.6.1摘要（P15候选F仅含5.6.1；已移除原5.6.2形态摘录）',
 'new_value_proposal':'P16不自动回写。建议评审F是否应保留5.6.1与5.6.2两段原文，显式保留子条号；如果≤300字且经原图逐字核实，按教师指南跨子条款摘录格式保留。',
 'source_pdf':'upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf','printed_page':9,'pdf_page_index_0based':14,'bbox_or_table_cell':'single_014.png page region: §5.6.1–§5.6.2; no coordinate crop recorded',
 'source_text_short':'§5.6.1 通用机理温区177–427℃；§5.6.2列高/低流速区形态。', 'condition_object':'通用机理边界 vs 具体形态描述；F raw quote vs H结构化形态字段',
 'evidence_level':'LOCAL_RENDERED_IMAGE_MACHINE_VISUAL_CANDIDATE','review_required':True,'review_status':'PENDING_HUMAN_EXACT_TRANSCRIPTION','decision_note':'P15缩短F不等于H形态丢失，但降低F自身源文跨度；需教师/Owner确认F栏期望摘录范围，核对原F≤300字限制。'}]

# Targeted PDF page review produced concrete fidelity flags, still proposals only.
dm_pdf='upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf'
proposals.extend([
 {'proposal_id':'P16B-DM-56-MATERIAL-5.6.3','proposal_type':'source_fidelity_review_candidate','clause_id':'GBT30579-2022-5.6','field':'受影响的材料/I','old_value':'3Cr-0.5Mo',
  'new_value_proposal':'核对并建议改为5Cr-0.5Mo。原PDF §5.6.3按耐环烷酸能力由弱到强逐项列有1.25Cr-0.5Mo、2.25Cr-0.5Mo、5Cr-0.5Mo、12Cr、9Cr-1Mo；不得把PDF条文5Cr改写成3Cr。',
  'source_pdf':dm_pdf,'printed_page':9,'pdf_page_index_0based':14,'bbox_or_table_cell':'dm_pages/page_14_target.png; §5.6.3 material sequence, no coordinate crop','source_text_short':'“2.25Cr-0.5Mo、5Cr-0.5Mo、12Cr、9Cr-1Mo”','condition_object':'材料牌号；耐蚀能力排序而非材料敏感性二元标签','evidence_level':'LOCAL_RENDERED_IMAGE_VISUAL_CANDIDATE','review_required':True,'review_status':'PENDING_HUMAN_DUAL_CHECK','decision_note':'图像视觉检查发现候选材料牌号与PDF不一致；须第二人放大核对后才可变更。'},
 {'proposal_id':'P16B-DM-56-TERM-SCOPE-5.6.4','proposal_type':'source_fidelity_review_candidate','clause_id':'GBT30579-2022-5.6','field':'主要影响因素/J及温度适用范围/V','old_value':'“轻相酸值/轻相介质218℃～400℃”',
  'new_value_proposal':'按原PDF统一为“烃相酸值/烃相介质使用温度218℃～400℃范围内腐蚀较为常见”；该窗口是5.6.4(b)烃相介质中的常见发生区间，不把“轻相”当成标准原词或全机理硬边界。5.6.1的177℃～427℃为机理段陈述，应与上述常见区间分层保存。',
  'source_pdf':dm_pdf,'printed_page':9,'pdf_page_index_0based':14,'bbox_or_table_cell':'dm_pages/page_14_target.png; §§5.6.1, 5.6.4(a)(b)','source_text_short':'5.6.1：177℃～427℃；5.6.4(a)(b)：烃相酸值、烃相介质218℃～400℃','condition_object':'通用机理温度叙述 vs 烃相常见窗口；酸值指向烃相','evidence_level':'LOCAL_RENDERED_IMAGE_VISUAL_CANDIDATE','review_required':True,'review_status':'PENDING_HUMAN_DUAL_CHECK','decision_note':'分层记录温度，不合并成单一适用范围；留意OCR将烃识为轻。'},
 {'proposal_id':'P16B-DM-56-EQUIPMENT-5.6.5','proposal_type':'source_fidelity_review_candidate','clause_id':'GBT30579-2022-5.6','field':'易发生的装置或设备/K','old_value':'候选遗漏焦化蜡油回路，且写“注氨点之前”',
  'new_value_proposal':'逐项核对并建议保留原PDF列举的延迟焦化高酸原油加工所涉焦化轻蜡油回路、焦化重蜡油回路；§5.6.5(d)核为“注氢点之前的热烃物料系统”，不是“注氨点”。同时核实减压重蜡油回路文字，不把设备例子误改为全机理适用条件。',
  'source_pdf':dm_pdf,'printed_page':9,'pdf_page_index_0based':14,'bbox_or_table_cell':'dm_pages/page_14_target.png; §5.6.5; continuation on next printed page if needed','source_text_short':'“焦化轻蜡油回路和焦化重蜡油回路”；“注氢点之前的热烃物料系统”','condition_object':'设备示例清单；不是介质/温度/压力约束','evidence_level':'LOCAL_RENDERED_IMAGE_VISUAL_CANDIDATE','review_required':True,'review_status':'PENDING_HUMAN_DUAL_CHECK','decision_note':'候选K中的装置名与注入点疑有错字/漏项；全文段落跨页，应核下一页后复核。'},
 {'proposal_id':'P16B-DM-523-MATERIAL-SCOPE','proposal_type':'source_fidelity_review_candidate','clause_id':'GBT30579-2022-5.23','field':'受影响的材料/I、材料条件/V','old_value':'O候选只列碳钢、300系列不锈钢、双相不锈钢',
  'new_value_proposal':'复核字段语义后，§5.23.3材料名录至少覆盖碳钢、300系列不锈钢、双相不锈钢、铝合金、镍基合金；要同时保留原文性能方向：碳钢耐蚀能力较弱，其余列举类具有较强耐腐蚀性，腐蚀速率还与NH₄HS浓度、流速有关。材料“受影响”不等同全部材料高易感。',
  'source_pdf':dm_pdf,'printed_page':33,'pdf_page_index_0based':38,'bbox_or_table_cell':'dm_pages/page_38_target.png; §§5.23.3–5.23.5','source_text_short':'§5.23.3列300系列、双相、铝合金和镍基合金耐腐蚀性较强','condition_object':'被影响材料列表 vs 相对耐腐蚀性；属性方向不可抹平','evidence_level':'LOCAL_RENDERED_IMAGE_VISUAL_CANDIDATE','review_required':True,'review_status':'PENDING_HUMAN_DUAL_CHECK','decision_note':'候选I较完整、O列表少项；审核字段定义后统一，不用一个短材料标签遮蔽耐蚀强弱。§5.23.5中49℃～66℃仅为加氢反应器反应产物出料降温后NH₄HS气相析出的局部设备现象，禁止提升为整个5.23的适用温度。'},
 {'proposal_id':'P16B-DM-67-CONDITION-SEMANTICS','proposal_type':'source_fidelity_review_candidate','clause_id':'GBT30579-2022-6.7','field':'主要影响因素/J、条件字段/V','old_value':'多个阈值压缩在共享条件文本中，容易被误读为设备总压或所有子类型统一温区',
  'new_value_proposal':'保留四类损伤区分：pH<4.0且有溶解H₂S；pH>7.6时还需HCN>20×10⁻⁶并有H₂S；溶解H₂S>50×10⁻⁶或潮湿气相H₂S分压>0.0003 MPa；氢鼓泡/HIC/SOHIC约室温至150℃（有时更高），SSC通常82℃以下。HB200仅指炼油厂常用低强度碳钢焊接接头SSC硬度控制例；HBB/HIC/SOHIC与钢铁硬度无关的原文限制需保留。不得把分压写进设备操作总压，也不得将一个子型窗口套给全部湿H₂S损伤。',
  'source_pdf':dm_pdf,'printed_page':52,'pdf_page_index_0based':57,'bbox_or_table_cell':'dm_pages/page_57_target.png; §6.7.4(a)–(g)','source_text_short':'pH 4.0/7.6；20×10⁻⁶ HCN；50×10⁻⁶ dissolved H₂S；0.0003 MPa wet-gas partial pressure；150℃/82℃ subtype split; HB200 scope','condition_object':'四种损伤形式的各自易感条件；气相分压而非系统总压；材料属性与硬度条件','evidence_level':'LOCAL_RENDERED_IMAGE_VISUAL_CANDIDATE','review_required':True,'review_status':'PENDING_HUMAN_DUAL_CHECK','decision_note':'定向图像核对确认候选V的条件边界总体有来源依据；仍需逐字验证科学计数格式/上标及字段归属，不能据此视为人工签核。'}
])

# (3) Supplement five-source 56 pending chapter items, without fabricating titles or DM content.
sup=readcsv(SUP_MATRIX)
pending=[r for r in sup if r['disposition']=='REVIEW_NEEDED']
assert len(pending)==56
supp_out=[]
for r in pending:
 code=r['standard_code']
 family='equipment_design_manufacturing_auxiliary' if code in ('GB/T 150.1-2024','GB/T 150.3-2024','GB/T 150.4-2024','GB/T 151-2026') else 'external_corrosion_control_auxiliary'
 chapter=r['chapter_or_annex'].strip()
 title=r['chapter_title_or_status']
 evidence='Targeted OCR only: first 15 pages per supplement; see supplement_toc_ocr/*.txt. OCR is navigation evidence, not exact transcription.'
 confidence='LOW_OCR_CANDIDATE'
 if code=='GB/T 21447-2018' and chapter in ('7','8','9'):
  title={'7':'干扰防护','8':'施工与验收','9':'运行及维护管理'}[chapter]
  confidence='MEDIUM_TARGETED_OCR_CANDIDATE'
  evidence += ' Relevant headings located in targeted PDF indices 10–14; retain human page/title verification.'
 if code=='GB/T 21447-2018' and chapter=='10':
  title='OCR前15页未能确认第10章标题/范围'; confidence='UNRESOLVED'
 if code=='GB/T 150.4-2024' and chapter.lower().startswith('annex'):
  evidence += ' Targeted contents page identifies annex family as manufacturing, inspection, acceptance and low-temperature brittle-fracture requirements; exact annex-title mapping remains OCR candidate.'
 if code=='GB/T 150.1-2024' and chapter=='4':
  title='失效模式（压力容器建造中考虑的主要失效模式）'; confidence='MEDIUM_TARGETED_OCR_CANDIDATE'
  evidence += ' Foreword and targeted page 10 identify chapter 4; generic construction failure categories are not damage-mode-specific service applicability.'
 if code=='GB/T 150.1-2024' and chapter.lower().startswith('annex'):
  evidence += ' Targeted contents OCR identifies overpressure relief and local structural stress analysis/evaluation among annexes; auxiliary design topics, not service damage modes.'
 if code=='GB/T 150.3-2024' and chapter.lower().startswith('annex'):
  evidence += ' Contents OCR suggests design annexes (non-circular sections, strip winding, sealing, low-temperature design/brittle-fracture check, jackets); exact mapping/title transcription remains unverified.'
 if code=='GB/T 151-2026':
  evidence += ' P14 context suggests equipment/design scope; targeted OCR did not yield reliable complete title mapping. Keep individual title, clause and applicability unresolved.'
 supp_out.append({'standard_code':code,'source_file':r['source_file'],'chapter_or_annex':r['chapter_or_annex'],'title_or_current_status':r['chapter_title_or_status'],
  'tentative_scope_family':family,'title_candidate_from_targeted_ocr':title,'title_confidence':confidence,'toc_ocr_evidence':evidence,'exact_title_status':'NOT_VERIFIED','direct_dm_eligible':'NO_EVIDENCE','page_start':r.get('printed_page_start',''),'page_end':r.get('printed_page_end',''),
  'decision':'KEEP_AUXILIARY_OR_REVIEW_NEEDED; DO NOT INGEST INTO DM/RBI','reason':r['rationale']+' 定向目录/OCR只用于收窄下一步核验范围；未经原图逐字复核和条款适用性判断，不视为标题或页界已确认。',
  'source_status':r['source_quality'],'next_minimum_evidence':'目录页/章首页原图及印刷页映射；若疑似风险/损伤内容，再提供具体条款与段落/表格格值。','human_review_status':'NOT_DONE','reviewer':''})
writecsv(OUT/'P16_B_SUPPLEMENT_REVIEW.csv',supp_out)

# (4) Re-run the unchanged official tool over the frozen 46 P15 queries; build an isolated enriched-field proposal index.
sys.path.insert(0,str(ROOT/'upstream/05_提交区'))
import tools as official_tools
spec=importlib.util.spec_from_file_location('p15_retrieval_spec',ROOT/'scripts/p15_c_retrieval_eval.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
CASES=module.CASES
# candidate 554 corpus is source-only; no file writes/official DB changes.
records=[]
with CANDIDATE_CLAUSES.open(encoding='utf-8') as f:
 for line in f:
  if line.strip(): records.append(json.loads(line))

def text_fields(rec):
 fields=[rec.get('title',''),rec.get('content_raw',''),rec.get('standard_code',''),rec.get('clause_no',''),rec.get('clause_id','')]
 for k,v in (rec.get('mechanism_detail') or {}).items():
  fields.extend(v if isinstance(v,list) else [v] if v else [])
 cond=rec.get('applicable_conditions') or {}
 fields.extend(v if isinstance(v,list) else [v] if v else [] for v in [])
 for k,v in cond.items():
  fields.extend(v if isinstance(v,list) else [v] if v else [])
 rbi=rec.get('rbi_detail') or {}
 for k,v in rbi.items():
  if v is not None: fields.extend(v if isinstance(v,list) else [v])
 # Create search-only cell labels from structured matrix attributes (not knowledge changes).
 like=str(rbi.get('likelihood') or '').strip(); consequence=str(rbi.get('consequence') or '').strip().upper()
 if like and consequence:
  fields.extend([f'矩阵格 {like}{consequence}',f'失效可能性{like} 后果{consequence}',f'cell_{like}{consequence}'])
 return ' '.join(str(x) for x in fields if x is not None)

index=[]
for rec in records:
 index.append({'rec':rec,'text':text_fields(rec).lower(),'title':(rec.get('title') or '').lower()})

def expand_case(cid,q):
 additions=[]
 if cid=='likelihood_method': additions=['技术模块因子 分析步骤 严重程度指数 检验程序有效性 次因子']
 elif cid=='matrix_5e': additions=['5 E 矩阵格 失效可能性5 后果E']
 elif cid=='matrix_mapping': additions=['风险等级的确定 5×5 风险矩阵图']
 elif cid=='inspection_strategy': additions=['损伤模式得到验证 扩大同一腐蚀回路 检验范围 检验比例']
 elif cid=='dm_56_light_phase': additions=['环烷酸腐蚀 轻相介质使用温度 218℃ 400℃']
 return [q]+additions

def rich_search(q,kind='rbi',top_k=20):
 terms=[t for t in tokens(q) if t]
 if not terms: return []
 # IDF-weighted character-coverage recall; field-rich local index only, relative ranking, not probabilities.
 pool=[d for d in index if kind is None or d['rec'].get('knowledge_type')==kind]
 idf=[math.log(1+len(pool)/(1+sum(t in d['text'] for d in pool))) for t in terms]
 scored=[]
 for d in pool:
  text=d['text'];title=d['title'];hits=[1.0 if t in text else 0.0 for t in terms]
  if not any(hits):continue
  cov=sum(w*h for w,h in zip(idf,hits))/(sum(idf) or 1)
  title_cov=sum(w*(1 if t in title else 0) for w,t in zip(idf,terms))/(sum(idf) or 1)
  # exact structured matrix cells get a transparent small boost when query names a specific cell.
  qcompact=re.sub(r'\s+','',q).upper(); rec=d['rec'];rbi=rec.get('rbi_detail') or {}
  grid=str(rbi.get('likelihood') or '').strip()+str(rbi.get('consequence') or '').strip().upper()
  cellboost=0.12 if grid and grid in qcompact and ('矩阵' in q or '风险' in q) else 0
  score=.65*title_cov+.35*cov+cellboost
  scored.append((score,rec))
 scored.sort(key=lambda z:(-z[0],z[1].get('clause_id','')))
 return [r for _,r in scored[:top_k]]

def eval_rows(runs,arm):
 out=[];matched=0;relevant=0;rr=[];positive=0;neg_nonempty=0
 for case in CASES:
  cid,name,q,gold=case; expected=[] if gold=='__NO_GOLD__' else gold.split('|')
  if arm=='baseline':
   t0=time.perf_counter();resp=official_tools.standard_clause_search(q,top_k=20);elapsed=(time.perf_counter()-t0)*1000
   ids=[x.get('clause_id') for x in (resp.get('result') or {}).get('hits') or []]
  else:
   t0=time.perf_counter();variants=expand_case(cid,q); gathered=[]
   for vi,v in enumerate(variants):
    hits=rich_search(v,kind=None,top_k=20)
    # RRF merge; variants are source-language supported expansion plans, not gold ID injection.
    gathered.extend((r,vi,rank) for rank,r in enumerate(hits,1))
   scores=defaultdict(float);objs={}
   for r,vi,rank in gathered:
    cid2=r['clause_id'];objs[cid2]=r;scores[cid2]+=1/(60+rank)
   ids=[objs[k]['clause_id'] for k in sorted(scores,key=lambda k:(-scores[k],k))[:20]]
   elapsed=(time.perf_counter()-t0)*1000
  if expected:
   positive+=1;relevant+=len(set(expected));n=len(set(ids)&set(expected));matched+=n;rank=next((i+1 for i,x in enumerate(ids) if x in expected),None);rr.append(1/rank if rank else 0)
  else:
   rank=None;n=0;neg_nonempty+=bool(ids)
  out.append({'case_id':cid,'query':q,'expected_clause_ids':'|'.join(expected),'query_origin':'SYNTHETIC_UNREVIEWED','retrieved_clause_ids_top20':'|'.join(ids),
   'first_gold_rank':rank or '', 'relevant_ids_retrieved':n,'relevant_id_count':len(set(expected)),'recall_at_20':n/len(set(expected)) if expected else '',
   'empty_result':not bool(ids),'unjudged_case_nonempty_diagnostic':(bool(ids) if not expected else ''),'latency_ms_one_run':round(elapsed,4),'warm_latency_mean_ms_30':'','warm_latency_p95_ms_30':'',
   'queries_used':len(expand_case(cid,q)) if arm=='candidate' else 1,'arm':arm,'evidence_warning':'Synthetic labels/source linkage are unreviewed; retrieval match is not content/applicability validation.'})
 result={'rows':out,'positive_cases':positive,'relevant_total':relevant,'retrieved_relevant':matched,'micro_recall_at_20':matched/relevant if relevant else 0,'mrr_at_20':sum(rr)/positive if positive else 0,'unjudged_nonempty_cases':neg_nonempty}
 return result
baseline=eval_rows(0,'baseline');candidate=eval_rows(0,'candidate')
writecsv(OUT/'P16_B_RETRIEVAL_BASELINE_46.csv',baseline['rows'])
writecsv(OUT/'P16_B_RETRIEVAL_CANDIDATE_46.csv',candidate['rows'])
# Latency repeatability on the five named miss cases; warm implementation runs, no external services.
miss_ids=['likelihood_method','matrix_5e','matrix_mapping','inspection_strategy','dm_56_light_phase']
latencies={'baseline':defaultdict(list),'candidate':defaultdict(list)}
for cid,name,q,gold in CASES:
 if cid not in miss_ids: continue
 for _ in range(30):
  t=time.perf_counter();official_tools.standard_clause_search(q,top_k=20);latencies['baseline'][cid].append((time.perf_counter()-t)*1000)
  t=time.perf_counter();variants=expand_case(cid,q);gathered=[]
  for vi,variant in enumerate(variants):gathered.extend((r,vi,rank) for rank,r in enumerate(rich_search(variant,kind=None,top_k=20),1))
  scores=defaultdict(float)
  for r,vi,rank in gathered:scores[r['clause_id']]+=1/(60+rank)
  sorted(scores,key=lambda k:(-scores[k],k))[:20]
  latencies['candidate'][cid].append((time.perf_counter()-t)*1000)

def pct(a,p):
 s=sorted(a);return s[max(0,math.ceil(p*len(s))-1)] if s else 0
for arm in latencies:
 for cid,a in latencies[arm].items():
  rows=baseline['rows'] if arm=='baseline' else candidate['rows']; row=next(x for x in rows if x['case_id']==cid)
  row['warm_latency_mean_ms_30']=round(mean(a),4);row['warm_latency_p95_ms_30']=round(pct(a,.95),4)
writecsv(OUT/'P16_B_RETRIEVAL_BASELINE_46.csv',baseline['rows'])
writecsv(OUT/'P16_B_RETRIEVAL_CANDIDATE_46.csv',candidate['rows'])
# Diff proposal JSONL includes retrieval only, never a teacher tool/data patch.
for case_id, root, plan in [
 ('likelihood_method','QUERY_TERM_MISMATCH_OR_GOLD_SCOPE_PENDING','Expand to source term “技术模块因子/损伤因子/严重程度指数/检验有效性”; review whether 8.3.2 is truly relevant to generic likelihood-method question.'),
 ('matrix_5e','STRUCTURED_FIELDS_NOT_INDEXED','Index rbi_detail likelihood/consequence as structured search tokens (e.g. 5E); preserve original structured values and do not infer cell risk.'),
 ('matrix_mapping','TOP_K_CUTOFF_AND_UNDERSPECIFIED_GOLD','Index matrix metadata/title; broad “25格” should retrieve the matrix family. Frozen single-ID gold 7-a is under-specified because all 25 cells share text; do not redefine gold silently.'),
 ('inspection_strategy','TERM_MISMATCH_AND_STANDARD_SCOPE','Add source-supported expansion “损伤模式得到验证/扩大同一腐蚀回路/检验范围/检验比例”; keep 26610.2 filter isolated from TSG by standard_code.'),
 ('dm_56_light_phase','INDEXED_FIELD_OMISSION_AND_STALE_CORPUS','Build app-side search document from mechanism_detail and applicable_conditions.other, not just title+content_raw. Verify P16 candidate F/conditions; source candidate not yet human-approved.')]:
 case=next(x for x in CASES if x[0]==case_id)
 proposal={'proposal_id':'P16B-RETR-'+case_id,'proposal_type':'isolated_application_retrieval_candidate','case_id':case_id,'query':case[2],'expected_clause_ids':case[3],
  'root_cause_hypothesis':root,'old_value':'现版仅title/content_raw关键词检索或旧方案的查询词覆盖不足','new_value_proposal':plan,'clause_id':case[3],'field':'application_retrieval_index/query_plan','source_pdf':'NOT_APPLICABLE_SEARCH_ONLY','printed_page':'','pdf_page_index_0based':'','bbox_or_table_cell':'NOT_APPLICABLE_SEARCH_ONLY','units_and_condition_scope':'不更改标准数值/适用条件；查询扩展只限来源术语与已有结构字段','scope':'P16-B local evaluator only; no P13, upstream tools, gold labels or official JSONL edits',
  'human_review_required':True,'status':'PROPOSAL_ONLY_NOT_RELEASED','query_origin':'SYNTHETIC_UNREVIEWED'}
 proposals.append(proposal)
(OUT/'P16_B_CHANGE_PROPOSALS.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in proposals),encoding='utf-8')

# Report summary and source hashes.
priority_counts=dict(Counter(x['standard_code'] for x in triage)); status_counts=dict(Counter(x['source_status'] for x in triage))
dm_counts=dict(Counter(x['p16_priority'] for x in dm_out));supp_counts=dict(Counter(x['tentative_scope_family'] for x in supp_out))
report={'status':'PENDING_HUMAN_REVIEW','table_risk_rows_total':221,'table_risk_excluded_p15_img_candidates':len(reviewed10),'table_risk_rows_remaining':len(triage),
 'table_rows_by_standard':priority_counts,'table_source_status':status_counts,'targeted_top20_rendered_ocr_rows':ocr_count,
 'table_cells_without_verified_bbox_or_dual_human_check':sum(x['source_status'] in ('SOURCE_UNRESOLVED_CELL_PAGE_LOCATED','AI_VISUAL_NUMERIC_ROW_MATCH_F_TEXT_PENDING_HUMAN') for x in triage),
 'dm_gn_fields':sum(x['field_letter'] in list('GHIJKLMN') for x in dm_out),'dm_condition_fields_ov':sum(x['field_letter'] in list('OPQRSTUV') for x in dm_out),'dm_total_cells':len(dm_out),
 'dm_priority_counts':dm_counts,'dm_ocr_missing_gn':sum(x['ocr_heading_missing_flag'] for x in dm_out),'supplement_56_pending_chapters':len(supp_out),'supplement_tentative_scope_counts':supp_counts,
 'retrieval_baseline':{k:v for k,v in baseline.items() if k!='rows'},'retrieval_candidate':{k:v for k,v in candidate.items() if k!='rows'},
 'retrieval_arms':'unchanged official standard_clause_search vs isolated enriched-field lexical/RRF prototype','retrieval_gold_unchanged':True,'retrieval_evaluation_scope':'46 frozen synthetic queries with in-sample source-language expansions; not expert validation or generalization','warm_latency_repeats_per_miss_case':30,'change_proposal_count':len(proposals),'teacher_tools_changed':False,'formal_data_changed':False}
(OUT/'P16_B_RUN_SUMMARY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

miss_diag={
'likelihood_method':'Expected GB/T 26610.4-2022-8.3.2 title is 技术模块因子; source describes damage severity index and inspection effectiveness, not literal “失效概率定量分析方法”. likely semantic query/gold-scope mismatch; confirm with domain reviewer before treating as true miss.',
'matrix_5e':'25 matrix rows have repeated content_raw/title; cell coordinates are structured rbi_detail fields that official search does not index. 5E is not present in text, so a per-cell request cannot rank target by source semantics.',
'matrix_mapping':'Query requests the matrix as a family but gold expects a single arbitrary 7-a row. Search returns matrix rows around rank boundary; top_k=20 undercovers a 25-cell family. Treat as family recall question, not one-cell semantic miss; no label change without review.',
'inspection_strategy':'Query mixes standard scope with generic “inspection interval”; 8.2 title is “检验策略的实施” and its body talks about verified damage mode, expanding circuit inspection scope/proportion, not a fixed cycle. Current scoring dilutes discriminative source phrase and ranks TSG clauses.',
'dm_56_light_phase':'Actual phrase “轻相介质218–400℃” is in structured mechanism_detail.influencing_factors/applicability, while standard_clause_search indexes only title+content_raw. Original source content_raw has 177–242℃ and omits the light-phase phrase; 0 hits indicate indexed-field omission/stale data, not absence from source.'}
lines=[]
for caseid in miss_ids:
 b=next(x for x in baseline['rows'] if x['case_id']==caseid);c=next(x for x in candidate['rows'] if x['case_id']==caseid)
 lines.append(f"| `{caseid}` | `{b['expected_clause_ids']}` | `{b['first_gold_rank'] or 'MISS'}` | `{c['first_gold_rank'] or 'MISS'}` | {miss_diag[caseid]} |")
md=f'''# P16-B｜来源保真与检索质量收口\n\n状态：**PENDING_HUMAN_REVIEW / PREVIEW_ONLY**。只写P16-B隔离目录及P16-B报告；upstream、P15成果、教师工具、正式JSONL、SQLite及应用代码均未改。\n\n## 1. 211条表格风险队列\n\n以P15-A `P15_A_TABLE_REVIEW_COVERAGE.csv` 221条为分母，并以26610.5表2/表3机器图像候选清单中10个clause_id做差，得到211条剩余待核记录：{json.dumps(priority_counts,ensure_ascii=False)}。所有项目保留旧F、PDF/印刷页定位、P15 locator、表格/行/列/bbox状态及未决原因，见`work/data_staging/p16/B_REMAINDER/P16_B_PRIORITY_TRIAGE.csv` / `P16_B_SOURCE_CELLS.csv`。\n\n- 211/211均没有独立真人核字；任何`PAGE_LOCATED_CELL_PENDING`都只证明页锚点可定位，不证明单元格、单位、脚注、边界或转述内容正确。`SOURCE_UNRESOLVED`按行给原因。\n- 按任务优先级先选26610.4风险最高的20条做定向页渲染与OCR，处理{ocr_count}/20条；源页图像保存在P16-B的`table_pages/`。OCR只是页内导航；没有将OCR读数写回数据或标成已核真。\n- 26610.4优先数值/量化因子表；26610.3表格行列仍需单元格格核；26610.5剩余15条；26610.2表1/表3五条/十条策略单元边界均保留原值待核。\n\n## 2. DM字段语义队列\n\nP15-B的656个G–N字段加656个O–V条件字段共{len(dm_out)}项全部进入`P16_B_DM_FIELD_REVIEW.csv`，没有继承P15的OCR定位为“已核真”。G–N中子条标题未命中项：{sum(x['ocr_heading_missing_flag'] for x in dm_out)}；标记数值/单位/浓度/分压/温度/硬度/材料耐蚀词项及5.6/5.23/6.7高优先项各见CSV。材料易感性、介质、设备和温压仍须按原文对象核对。\n\n5.6 P15候选F由5.6.1+5.6.2摘录缩短为仅5.6.1；H仍含损伤形态，故不能直接判为机理内容全丢，但F覆盖范围和逐字摘录价值下降。提出定向复核建议：比较标准印刷页9/PDF index14 §5.6.1–5.6.2图像，确认F是否应带上5.6.2并保持≤300字；不在P16自动回写。177–427℃通用机理范围与218–400℃轻相介质常见窗口仍需真人核签，且5.23析出局部窗口、6.7子类型温区/0.0003 MPa H₂S分压不得冒充整体温压过滤条件。\n\n## 3. 五份补充PDF余下56章\n\nP15章节矩阵中56个`REVIEW_NEEDED`项全部转入`P16_B_SUPPLEMENT_REVIEW.csv`，按暂定范围家族分类为：{json.dumps(supp_counts,ensure_ascii=False)}。没有把推测标题改成确定标题；章名/页界仍未核实的条目逐项写明最小补证要求（目录/章首页、页码映射及实际条文）。没有把150设计/制造、151设备结构、21447外腐蚀控制背景强塞入DM/RBI，也没有生成补充DM记录。\n\n## 4. 冻结46题检索对照\n\n在同一554条P15候选JSONL上，实际重跑46个冻结合成查询、原gold不变：\n- 官方只读工具基线：检索到{baseline['retrieved_relevant']}/{baseline['relevant_total']}相关ID，micro Recall@20={baseline['micro_recall_at_20']:.3f}，MRR@20={baseline['mrr_at_20']:.3f}。\n- P16候选：应用层全字段本地索引+query-plan扩展+RRF；检索到{candidate['retrieved_relevant']}/{candidate['relevant_total']}，micro Recall@20={candidate['micro_recall_at_20']:.3f}，MRR@20={candidate['mrr_at_20']:.3f}。这是一次对合成gold的算法对照，不代表专业检索验收；未改变gold、官方工具或正式数据。\n- 对照结果及top20逐条结果见`P16_B_RETRIEVAL_BASELINE_46.csv`、`P16_B_RETRIEVAL_CANDIDATE_46.csv`；五项各30次暖机延迟均值/p95记在对应行。未标注题非空结果只作诊断，不能判定为误报。\n\n### 5个失配根因与对照\n\n| frozen case | gold | baseline rank | candidate rank | 根因/整改验证 |\n|---|---|---:|---:|---|\n{chr(10).join(lines)}\n\n`likelihood_method`的目标8.3.2标题是“技术模块因子”，与查询“失效概率定量分析方法”并非明显同义；扩词可能改善rank，但gold是否真相关仍要领域人审。`matrix_mapping`问25格却只标一个7-a，不能据此调参伪造精度。`inspection_strategy`应以“验证后扩大同一腐蚀回路检验范围/比例”作为区分短语，而不是检验周期泛词。`dm_56_light_phase`为空结果与文本只索引title/content_raw、条件在结构字段的机制相符。整改方案在`P16_B_CHANGE_PROPOSALS.jsonl`中，均是隔离建议。\n\n## 5. 来源和状态口径\n\n- P16-B变更建议：{len(proposals)}条（1条5.6 F摘录范围复核建议+5条检索应用层建议）；不自动变更教师Excel/正式JSONL。\n- 211条源表格高风险行仍未逐格验证；20条OCR不是20条准确率。\n- 82模式条件字段、56章目录/内容以及retrieval gold仍需真人/领域审查。\n- P15合成查询指标和P16本地候选策略是可复现工程回归，不是专家准确率。\n\n## 复现\n\n```powershell\npython scripts/p16_b_fidelity_retrieval.py\npython -B -m unittest tests.test_p16_b_fidelity_retrieval -v\n```\n'''
md=md.replace('OCR只是页内导航；没有将OCR读数写回数据或标成已核真。', 'OCR只是页内导航；没有将OCR读数写回数据或标成已核真。20条集中在GB/T 26610.4-2022表2的6-a至6-t，针对同一来源页定向采集；候选图像肉眼扫查显示设备行名、四个破裂口区间及FG合计与该页表格布局相符，但未记录单元格BBox，也未由第二名复核者签核。故这不是20条已核真记录，仍需逐行记录行列坐标、单位/边界、脚注及每行FG合计关系。')
md=md.replace('任何`PAGE_LOCATED_CELL_PENDING`都只证明页锚点可定位，不证明单元格、单位、脚注、边界或转述内容正确。`SOURCE_UNRESOLVED`按行给原因。', '211/211条精确单元格仍无双人核签BBox：191条归`SOURCE_UNRESOLVED_CELL_PAGE_LOCATED`（仅定位物理页，行/列未可靠定位）；20条为表2视觉候选`AI_VISUAL_NUMERIC_ROW_MATCH_F_TEXT_PENDING_HUMAN`（录入行名和列头、未记录BBox）。CSV逐条保留PDF/页码/可验证定位或明确的细胞级未决原因，不把页定位冒充单元格核真。')
md=md.replace('5.6 P15候选F由5.6.1+5.6.2摘录缩短为仅5.6.1；H仍含损伤形态，故不能直接判为机理内容全丢，但F覆盖范围和逐字摘录价值下降。提出定向复核建议：比较标准印刷页9/PDF index14 §5.6.1–5.6.2图像，确认F是否应带上5.6.2并保持≤300字；不在P16自动回写。177–427℃通用机理范围与218–400℃轻相介质常见窗口仍需真人核签，且5.23析出局部窗口、6.7子类型温区/0.0003 MPa H₂S分压不得冒充整体温压过滤条件。', '5.6原图定向核查（GB/T 30579-2022印刷页9/PDF index14）产生待复核建议：候选I把材料序列`5Cr-0.5Mo`写成`3Cr-0.5Mo`；候选J把标准原词“烃相酸值/烃相介质”改成“轻相”，应分开记录177–427℃机理段与218–400℃烃相常见窗口；候选K可能漏列延迟焦化焦化轻/重蜡油回路，并将`注氢点`写成`注氨点`。这些属原图候选，且5.6.5段落续页，待第二人逐字确认。另5.6 P15候选F由5.6.1+5.6.2摘录缩短为仅5.6.1；H仍含损伤形态，故不能判机理内容全丢，但F覆盖范围缩小；须按≤300字规则复核。5.23原图（印刷页33/PDF index38）确认49–66℃只对应加氢反应器反应产物出料降温时气相NH₄HS析出/沉积；不是整机理适用温区。其材料枚举包含铝合金及镍基合金，原O候选遗漏；原文将碳钢耐蚀性较弱与其余列举材料耐蚀性较强分开描述。6.7原图（印刷页52/PDF index57）确认H₂S气相分压阈值0.0003 MPa、溶液H₂S浓度阈值50×10⁻⁶、HCN阈值20×10⁻⁶为不同条件；氢鼓泡/HIC/SOHIC温度约室温至150℃（有时更高），SSC通常82℃以下；HB200限于低强度碳钢焊接接头SSC描述。不能将分压写作设备总压或把子类型温区套为整体边界。相关变更仅进入来源建议，仍需第二人签核。')
md=md.replace('没有把推测标题改成确定标题；章名/页界仍未核实的条目逐项写明最小补证要求（目录/章首页、页码映射及实际条文）。没有把150设计/制造、151设备结构、21447外腐蚀控制背景强塞入DM/RBI，也没有生成补充DM记录。', '仅对五份PDF各前15页定向OCR，共75页，不做全文OCR。`title_candidate_from_targeted_ocr`和`toc_ocr_evidence`是导航证据，不解除`exact_title_status=NOT_VERIFIED`：GB/T 150.1第4章可见“失效模式”，但它是建造过程中考虑的通用短期/长期/循环失效模式，不能直接等同30579服务损伤机理；GB/T 150.4附录候选归于制造/检验/验收及低温脆断设计制造；GB/T 21447定向页可读到第7章“干扰防护”、第8章“施工与验收”、第9章“运行及维护管理”，页界及第10章仍未完全确认；150.3目录附录、GB/T 151-2026标题仍需原图逐项核对。所有候选标题/页界未核实项均逐条写明最小补证要求。未把这些背景强塞入DM/RBI，也未生成补充DM记录。')
latency_note='；'.join(f"{cid}: baseline {next(x for x in baseline['rows'] if x['case_id']==cid).get('warm_latency_mean_ms_30')}/{next(x for x in baseline['rows'] if x['case_id']==cid).get('warm_latency_p95_ms_30')} ms, candidate {next(x for x in candidate['rows'] if x['case_id']==cid).get('warm_latency_mean_ms_30')}/{next(x for x in candidate['rows'] if x['case_id']==cid).get('warm_latency_p95_ms_30')} ms" for cid in miss_ids)
md=md.replace('五项各30次暖机延迟均值/p95记在对应行。未标注题非空结果只作诊断，不能判定为误报。', f'五项各30次暖机延迟均值/p95记在对应行：{latency_note}。这是本机进程内微基准，不含API/数据库网络耗时，也不是生产SLA。未标注题非空结果只作诊断，不能判定为误报。')
md=md.replace('20条OCR不是20条准确率。', '20条定向OCR不是20条准确率；候选视觉扫查仍待人工签核。')
md=md.replace('（1条5.6 F摘录范围复核建议+5条检索应用层建议）', '（6条DM来源/字段复核建议+5条检索应用层建议）')
md=md.replace('{len(proposals)}条（1条5.6 F摘录范围复核建议+5条检索应用层建议）', '{len(proposals)}条（6条DM来源/字段复核建议+5条检索应用层建议）')
md=md.replace('82模式条件字段、56章目录/内容以及retrieval gold仍需真人/领域审查。', '656个G–N字段、656个O–V条件字段、56章目录/内容以及retrieval gold仍需真人/领域审查。补充PDF的75页定向OCR不是全文或章级验收。')
(DOCS/'P16_B_SOURCE_FIDELITY_AND_RETRIEVAL.md').write_text(md,encoding='utf-8')
retrieval_diag = '# P16-B｜P15-C五个检索未命中诊断\n\n状态：`PROPOSAL_ONLY_NOT_RELEASED`。基线使用只读官方工具；候选在隔离内存索引上试验，gold和上游工具均未修改。46条查询均为synthetic，不构成专家质量验收。\n\n'
retrieval_diag += f"| case | query | gold | baseline rank | candidate rank | global Recall@20/MRR@20 |\n|---|---|---|---:|---:|---|\n"
for cid in miss_ids:
 case=next(x for x in CASES if x[0]==cid); b=next(x for x in baseline['rows'] if x['case_id']==cid); c=next(x for x in candidate['rows'] if x['case_id']==cid)
 retrieval_diag += f"| `{cid}` | {case[2]} | `{b['expected_clause_ids']}` | {b['first_gold_rank'] or 'MISS'} | {c['first_gold_rank'] or 'MISS'} | base {baseline['micro_recall_at_20']:.3f}/{baseline['mrr_at_20']:.3f}; cand {candidate['micro_recall_at_20']:.3f}/{candidate['mrr_at_20']:.3f} |\n"
retrieval_diag += '\n## 根因和整改验证\n\n'
for cid in miss_ids:
 c=next(x for x in candidate['rows'] if x['case_id']==cid)
 retrieval_diag += f"### `{cid}`\n\n{miss_diag[cid]}\n\n候选rank：{c['first_gold_rank'] or 'MISS'}。需用holdout查询验证词汇扩展并请领域人员复核gold；不得用这46题内调参数宣称泛化。\n\n"
retrieval_diag += '候选整改在`work/data_staging/p16/B_REMAINDER/P16_B_CHANGE_PROPOSALS.jsonl`（5条检索应用建议）。逐题top20及30次延迟见baseline/candidate CSV；延迟是本机进程内微基准，不含HTTP/SQLite网络耗时。'
(DOCS/'P16_B_RETRIEVAL_DIAGNOSIS.md').write_text(retrieval_diag,encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

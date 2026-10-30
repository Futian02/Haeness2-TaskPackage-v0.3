"""Assemble a cautious chapter/section coverage view from A/B/C machine ledgers."""
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'work'/'data_staging'/'p14'
AG=STAGE/'agents'
OUT=ROOT/'docs'/'data_quality'/'P14_CHAPTER_COVERAGE_MATRIX.csv'

def read_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    rows=[]
    summary=json.loads((AG/'A'/'dm30579_pilot_and_screen_summary.json').read_text(encoding='utf-8'))
    dm={}
    for r in read_csv(AG/'A'/'dm30579_existing82_row_screen.csv'):
        dm.setdefault(str(r['chapter']),[]).append(r)
    for chapter,count in sorted(summary['chapter_counts'].items(),key=lambda x:int(x[0])):
        recs=dm.get(chapter,[])
        rows.append({'standard_code':'GB/T 30579-2022','source_pdf':'02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf',
          'chapter_or_section':chapter,'chapter_title':'machine chapter number only; title requires PDF visual audit',
          'pdf_pages_in_standard':163,'existing_record_count':count,'machine_clauses':';'.join(sorted({x['clause_id'] for x in recs})),
          'printed_page_min':min((int(x['printed_page']) for x in recs if x['printed_page'].isdigit()),default=''),
          'printed_page_max':max((int(x['printed_page']) for x in recs if x['printed_page'].isdigit()),default=''),
          'coverage_status':'existing row numbering matches expected chapter counts; content/appendix completeness unverified',
          'candidate_or_disposition':'82 baseline records preserved in staging; no additions without source verification',
          'evidence_level':'machine_located/unreviewed','human_visual_review':'not complete','human_reviewer':''})
    rows.append({'standard_code':'GB/T 30579-2022','source_pdf':'02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf',
      'chapter_or_section':'Appendix A','chapter_title':'damage mode index / appendix audit pending','pdf_pages_in_standard':163,
      'existing_record_count':'','machine_clauses':'','printed_page_min':'','printed_page_max':'',
      'coverage_status':'not independently enumerated against original PDF','candidate_or_disposition':'cross-check mandatory list and Annex A against all 82 records',
      'evidence_level':'unreviewed','human_visual_review':'not complete','human_reviewer':''})
    b=read_csv(AG/'B'/'rbi_existing_rows_machine_audit.csv')
    meta=json.loads((AG/'B'/'rbi_machine_audit_summary.json').read_text(encoding='utf-8'))
    by=defaultdict(list)
    for r in b:
        major=(r.get('clause_no') or '').split('.')[0]
        by[(r.get('standard_code') or '',major)].append(r)
    source_map={
      'GB/T 26610.1-2022':'01_RBI标准/GBT26610.1-2022_基本要求和实施程序.pdf',
      'GB/T 26610.2-2022':'01_RBI标准/GBT26610.2-2022_基于风险的检验策略.pdf',
      'GB/T 26610.3-2014':'01_RBI标准/GBT26610.3-2014_风险的定性分析方法.pdf',
      'GB/T 26610.4-2022':'01_RBI标准/GBT26610.4-2022_失效可能性定量分析方法.pdf',
      'GB/T 26610.5-2022':'01_RBI标准/GBT26610.5-2022_失效后果定量分析方法.pdf',
      'TSG 21-2016':'01_RBI标准/补充规范/TSG21-2016_固定式压力容器安全技术监察规程.pdf'}
    for (std,major),group in sorted(by.items()):
        exact=sum(x.get('quote_machine_match')=='exact_normalized_page' for x in group)
        fragment=sum(x.get('quote_machine_match')=='prefix_or_suffix_fragment' for x in group)
        nomatch=sum(x.get('quote_machine_match')=='none' for x in group)
        flagged=sum(str(x.get('table_explanation_pattern','')).lower()=='true' for x in group)
        rows.append({'standard_code':std,'source_pdf':source_map.get(std,''),'chapter_or_section':major,
          'chapter_title':'clause prefix present in observed workbook; full PDF chapter inventory not confirmed',
          'pdf_pages_in_standard':next((x['pdf_pages'] for x in meta['source_pdf_metadata'] if x['standard_code']==std),''),
          'existing_record_count':len(group),'machine_clauses':';'.join(sorted({x['clause_no'] for x in group})),
          'printed_page_min':min((int(x['page']) for x in group if str(x.get('page','')).isdigit()),default=''),
          'printed_page_max':max((int(x['page']) for x in group if str(x.get('page','')).isdigit()),default=''),
          'coverage_status':f'workbook prefix scanned; PDF exact-match hints {exact}, fragment {fragment}, no-match {nomatch}; not a quote accuracy score',
          'candidate_or_disposition':f'{flagged} rows have a table-explanation heuristic flag; preserve all, queue visual review',
          'evidence_level':'machine_located/unreviewed','human_visual_review':'not complete','human_reviewer':''})
    for c in read_csv(AG/'C'/'supplement_chapter_coverage.csv'):
        rows.append({'standard_code':c.get('standard_code'),'source_pdf':c.get('source_file'),
          'chapter_or_section':c.get('chapter_or_annex'),'chapter_title':c.get('chapter_title_or_status'),
          'pdf_pages_in_standard':'','existing_record_count':0,'machine_clauses':'',
          'printed_page_min':c.get('printed_page_start'),'printed_page_max':c.get('printed_page_end'),
          'coverage_status':c.get('coverage_status'),'candidate_or_disposition':c.get('candidate_or_disposition'),
          'evidence_level':'machine_scan_only','human_visual_review':c.get('visual_review'),'human_reviewer':c.get('human_reviewer')})
    fields=['standard_code','source_pdf','chapter_or_section','chapter_title','pdf_pages_in_standard','existing_record_count','machine_clauses','printed_page_min','printed_page_max','coverage_status','candidate_or_disposition','evidence_level','human_visual_review','human_reviewer']
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print(f'chapter_or_section_rows={len(rows)} output={OUT}')
if __name__=='__main__':main()

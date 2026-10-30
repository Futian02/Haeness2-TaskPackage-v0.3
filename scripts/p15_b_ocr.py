from __future__ import annotations
import csv, json, re, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IMG=ROOT/'upstream/02_损伤机理参考/_rendered'
OUT=ROOT/'work/data_staging/p15/B_DM'
CACHE=OUT/'page_ocr'
CACHE.mkdir(parents=True,exist_ok=True)

def ocr(i):
 p=CACHE/f'single_{i:03d}.txt'
 if p.exists() and p.stat().st_size: return i,p.read_text(encoding='utf-8')
 image=IMG/f'single_{i:03d}.png'
 if not image.exists(): return i,''
 r=subprocess.run(['tesseract',str(image),'stdout','-l','chi_sim+eng','--psm','6'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
 txt=r.stdout
 p.write_text(txt,encoding='utf-8')
 return i,txt

with ThreadPoolExecutor(max_workers=6) as pool:
 results=list(pool.map(ocr,range(163)))
alltext={i:t for i,t in results}
(OUT/'DM_PAGE_OCR.jsonl').write_text(''.join(json.dumps({'pdf_page_index_0based':i,'pdf_page_number_1based':i+1,'image':f'upstream/02_损伤机理参考/_rendered/single_{i:03d}.png','engine':'Tesseract 5.5.2 chi_sim+eng psm6','text':t},ensure_ascii=False)+'\n' for i,t in sorted(alltext.items())),encoding='utf-8')
# Parse per subclause text as OCR-only locator. It is explicitly not exact/transcribed evidence.
with (ROOT/'work/data_staging/p14/agents/A/dm30579_existing82_row_screen.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
items=[]
for row in rows:
 cid=row['clause_id'].replace('GBT30579-2022-','')
 start=int(row['pdf_page_index']); start_print=int(row['printed_page'])
 # subsection text can span multiple pages until next subclause; bounded at 3 PDF pages to avoid OCR section bleed.
 for n in range(1,9):
  label=f'{cid}.{n}'
  # collect from section start to next mechanism's start; use up to 3 pages after the known row page.
  page_text='\n'.join(alltext.get(p,'') for p in range(start,min(163,start+3)))
  # Keep OCR page text around heading if found; OCR often damages punctuation/decimal separators.
  norm=lambda s:re.sub(r'\s+','',s).replace('．','.').replace('。','.')
  nt=norm(page_text); nl=norm(label)
  pos=nt.find(nl)
  found=pos>=0
  snippet=''
  if found:
   # Cut 650 normalized chars, sufficient for machine locator only.
   snippet=nt[pos:pos+650]
  items.append({'clause_id':cid,'field_letter':chr(ord('G')+n-1),'source_subclause':label,'printed_page_start':start_print,
   'pdf_page_index_0based':start,'ocr_heading_found':found,'ocr_snippet':snippet,
   'ocr_status':'OCR_LOCATOR_ONLY_NOT_HUMAN_VERIFIED' if found else 'OCR_HEADING_NOT_FOUND_REVIEW_NEEDED',
   'bbox_or_table_cell':None})
with (OUT/'DM_SUBCLAUSE_OCR_LOCATORS.jsonl').open('w',encoding='utf-8') as f:
 for x in items:f.write(json.dumps(x,ensure_ascii=False)+'\n')
print(json.dumps({'pages':len(alltext),'subclause_slots':len(items),'ocr_heading_hits':sum(x['ocr_heading_found'] for x in items),'cache_files':sum(1 for _ in CACHE.glob('*.txt'))},ensure_ascii=False))

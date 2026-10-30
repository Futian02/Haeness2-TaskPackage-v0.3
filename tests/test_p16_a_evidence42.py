from __future__ import annotations
import csv, json, re
from pathlib import Path
import fitz

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/data_staging/p16/A_CHANGED_42'

def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def test_42_cards_cover_all_diff_ids_and_human_fields_blank():
    diffs=rows(ROOT/'work/data_staging/p15/merged/P15_C_CANDIDATE_JSONL_DIFF.csv')
    review=rows(OUT/'P16_A_REVIEW42.csv')
    assert len({r['clause_id'] for r in diffs})==42
    assert len(review)==42 and {r['clause_id'] for r in review}=={r['clause_id'] for r in diffs}
    for r in review:
        assert all(r[k]=='' for k in ['human_result','human_applicability_supported','human_reviewer','human_datetime','human_confirmed_printed_page','human_correction','human_signature'])
        assert r['machine_review_label']=='AI_VISUAL_CANDIDATE'
        assert r['review_status']=='PENDING_HUMAN'
        card=OUT/r['card_path']
        assert card.exists() and 'AI_VISUAL_CANDIDATE' in card.read_text(encoding='utf-8')
        assert '旧值' in card.read_text(encoding='utf-8') and '候选新值' in card.read_text(encoding='utf-8')

def test_73_cell_changes_reconciled_and_each_clause_card_counts():
    audit=rows(OUT/'P16_A_CELL_AUDIT.csv')
    ach=rows(ROOT/'work/data_staging/p15/A_RBI/P15_A_FIELD_CHANGELOG.csv')
    bch=rows(ROOT/'docs/data_quality/P15_B_FIELD_CHANGELOG.csv')
    assert len(audit)==73 and len(ach)==64 and len(bch)==9
    review=rows(OUT/'P16_A_REVIEW42.csv')
    for r in review:
        assert int(r['cell_changes'])==sum(x['clause_id']==r['clause_id'] for x in audit)

def test_all_cited_page_indices_and_local_images_exist():
    inv=rows(OUT/'P16_A_PAGE_INVENTORY.csv')
    assert len(inv)==42
    for r in inv:
        src=ROOT/r['src']; assert src.exists()
        indexes=[int(v) for v in r['indices'].split(';') if v]
        with fitz.open(src) as pdf:
            assert indexes and all(0<=i<len(pdf) for i in indexes)
        images=[v for v in r['images'].split(';') if v]
        assert len(images)==len(indexes)
        assert all((OUT/'pages'/img).exists() for img in images)

def test_matrix_25_cells_match_source_color_map_and_risk_labels():
    objs={}
    for line in (ROOT/'work/data_staging/p15/merged/clauses_candidate.jsonl').open(encoding='utf-8'):
        o=json.loads(line); objs[o['clause_id']]=o
    grid={1:{'A':'低风险','B':'低风险','C':'中风险','D':'中风险','E':'中高风险'},2:{'A':'低风险','B':'低风险','C':'中风险','D':'中风险','E':'中高风险'},3:{'A':'低风险','B':'低风险','C':'中风险','D':'中高风险','E':'高风险'},4:{'A':'中风险','B':'中风险','C':'中高风险','D':'中高风险','E':'高风险'},5:{'A':'中高风险','B':'中高风险','C':'中高风险','D':'高风险','E':'高风险'}}
    entries=[o for cid,o in objs.items() if cid.startswith('GBT26610.3-2014-7-')]
    assert len(entries)==25
    for o in entries:
        rd=o['rbi_detail']; assert rd['risk_level']==grid[int(rd['likelihood'])][rd['consequence']]

def test_priority_table_values_and_review_only_proposal():
    cards=list((OUT/'cards').glob('*.html'))
    assert len(cards)==42
    for cid in [f'GBT26610.5-2022-表{t}-{g}' for t in (2,3) for g in 'abcde']:
        card=next(p for p in cards if f'证据核验卡：{cid}' in p.read_text(encoding='utf-8'))
        content=card.read_text(encoding='utf-8')
        assert '单位为平方米' in content if '表2' in cid else '单位为元' in content
    proposals=[json.loads(line) for line in (OUT/'P16_A_PROPOSED_CORRECTIONS.jsonl').read_text(encoding='utf-8').splitlines()]
    proposal=next(p for p in proposals if p['clause_id']=='GBT30579-2022-5.6')
    locator=next(p for p in proposals if p['clause_id']=='TSG21-2016-8.3.12')
    assert proposal['data_mutation'] is False and proposal['machine_conclusion']=='AMBIGUOUS'
    assert '5.6.2' in proposal['observed_change']
    assert locator['visually_verified_locator']['pdf_page_index_0based']==83 and locator['data_mutation'] is False
    tsg=next(p for p in cards if 'TSG21-2016-8.3.12' in p.read_text(encoding='utf-8'))
    assert 'CONTRADICTS' in tsg.read_text(encoding='utf-8') and 'TSG21-2016___p083.png' in tsg.read_text(encoding='utf-8')
    assert 'HUMAN_VERIFIED' not in ''.join(p.read_text(encoding='utf-8') for p in cards)

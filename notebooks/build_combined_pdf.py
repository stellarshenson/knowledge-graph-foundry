import sys, json, re; sys.path.insert(0, 'notebooks')
import warnings; warnings.filterwarnings('ignore')
from parser_harness import *
from pypdf import PdfReader, PdfWriter
import pdfplumber, yaml

docnames, rows = load_entities()
pm = json.loads((CACHE / 'page_map.json').read_text())

# --- numeric floor pages from probe gold evidence ---
probes = yaml.safe_load(open('tests/probes/cpap-probe-set.yml'))
# per-page text cache for gold source docs
def page_texts(doc):
    try: rd = PdfReader(str(PDFDIR / doc)); pp = [(pg.extract_text() or '') for pg in rd.pages]
    except Exception: pp = []
    try:
        with pdfplumber.open(str(PDFDIR / doc)) as pdf: pb = [(pg.extract_text() or '') for pg in pdf.pages]
    except Exception: pb = [''] * len(pp)
    n = max(len(pp), len(pb)); out = []
    for i in range(n):
        a = (pp[i] if i < len(pp) else '') + '\n' + (pb[i] if i < len(pb) else '')
        out.append((norm(a), nospace(a)))
    return out

gold_src = {}
for pr in probes:
    for g in (pr.get('gold_evidence') or []):
        for src in (pr.get('sources') or []):
            gold_src.setdefault(src, []).append(g)

numeric_pages = {}  # doc -> set(pages) containing gold strings
gold_page_map = []  # (gold, doc, pages)
ptcache = {}
for doc, golds in gold_src.items():
    if doc not in set(docnames):
        continue
    pts = ptcache.setdefault(doc, page_texts(doc))
    for g in golds:
        hits = [i for i, (pn, ps) in enumerate(pts) if present_in(g, pn, ps)]
        gold_page_map.append(dict(gold=g, doc=doc, pages=hits))
        if hits:
            numeric_pages.setdefault(doc, set()).update(hits)

# --- assemble combined page set: loss + absent + numeric-floor ---
want = {}  # doc -> set(pages)
for d, pgs in pm['loss_pages'].items(): want.setdefault(d, set()).update(pgs)
for d, pgs in pm['absent_pages'].items(): want.setdefault(d, set()).update(pgs)
for d, pgs in numeric_pages.items(): want.setdefault(d, set()).update(pgs)

manifest = []  # combined page idx -> (doc, src_page)
writer = PdfWriter()
readers = {}
for d in sorted(want):
    rd = readers.setdefault(d, PdfReader(str(PDFDIR / d)))
    for p in sorted(want[d]):
        if p < len(rd.pages):
            writer.add_page(rd.pages[p])
            manifest.append(dict(doc=d, page=p))
outpdf = CACHE / 'combined_vlm.pdf'
with open(outpdf, 'wb') as fh:
    writer.write(fh)

(CACHE / 'combined_manifest.json').write_text(json.dumps(manifest, indent=1))
(CACHE / 'numeric_floor.json').write_text(json.dumps(dict(
    numeric_pages={d: sorted(s) for d, s in numeric_pages.items()},
    gold_page_map=gold_page_map), indent=1))

print('combined pages:', len(manifest))
print('docs in combined:', len(want))
print('numeric-floor pages per doc:')
for d, s in numeric_pages.items():
    print(f'   {sorted(s)}  {d}')
print('gold strings located:', sum(1 for g in gold_page_map if g['pages']), '/', len(gold_page_map))

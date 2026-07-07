import sys, json, re; sys.path.insert(0, 'notebooks')
import warnings; warnings.filterwarnings('ignore')
from parser_harness import *
from pypdf import PdfReader
import pdfplumber

docnames, rows = load_entities()
tri = {p: load_text(p) for p in TRIO}
tm = {p: norm_maps(tri[p]) for p in TRIO}

def found_any(name, docs, p):
    return any(present_in_doc(name, dn, tm[p]) for dn in docs)

# rebuild parse-lost with credited docs
parse_lost = []
for r in rows:
    fp = found_any(r['name'], r['docs'], 'pymupdf4llm')
    fa = found_any(r['name'], r['docs'], 'pdfplumber') or found_any(r['name'], r['docs'], 'pypdf')
    if (not fp) and fa:
        credit = [dn for dn in r['docs']
                  if not present_in_doc(r['name'], dn, tm['pymupdf4llm'])
                  and (present_in_doc(r['name'], dn, tm['pdfplumber']) or present_in_doc(r['name'], dn, tm['pypdf']))]
        parse_lost.append(dict(name=r['name'], credit=credit))
absent = [r for r in rows if not any(found_any(r['name'], r['docs'], p) for p in TRIO)]
ss_family = [r for r in absent if re.search(r'sleepstyle', r['name'], re.I)]

# per-page text (pypdf + pdfplumber) for the docs we care about
care = set()
for pl in parse_lost:
    care |= set(pl['credit'])
for r in ss_family:
    care |= set(r['docs'])
pagetext = {}  # doc -> [ (norm_page, nospace_page) per page ]
for d in care:
    pages = []
    try:
        rd = PdfReader(str(PDFDIR / d))
        pp = [(pg.extract_text() or '') for pg in rd.pages]
    except Exception:
        pp = []
    try:
        with pdfplumber.open(str(PDFDIR / d)) as pdf:
            pb = [(pg.extract_text() or '') for pg in pdf.pages]
    except Exception:
        pb = [''] * len(pp)
    n = max(len(pp), len(pb))
    for i in range(n):
        a = (pp[i] if i < len(pp) else '') + '\n' + (pb[i] if i < len(pb) else '')
        pages.append((norm(a), nospace(a)))
    pagetext[d] = pages

def locate(name, doc):
    pages = pagetext.get(doc, [])
    hits = [i for i, (pn, ps) in enumerate(pages) if present_in(name, pn, ps)]
    return hits

# loss-set page map
loss_pages = {}  # doc -> set of pages, plus name->pages
name_pages = []
for pl in parse_lost:
    for d in pl['credit']:
        hits = locate(pl['name'], d)
        name_pages.append(dict(name=pl['name'], doc=d, pages=hits, kind='loss'))
        loss_pages.setdefault(d, set()).update(hits)

# absent-family: not in text layer; anchor via 'SleepStyle' / 'Fisher & Paykel SleepStyle'
absent_pages = {}
for r in ss_family:
    for d in r['doc'] if False else r['docs']:
        anchor_hits = set()
        for anc in ['Fisher & Paykel SleepStyle', 'SleepStyle', 'Sleepstyle', 'F&P SleepStyle']:
            anchor_hits.update(locate(anc, d))
        name_pages.append(dict(name=r['name'], doc=d, pages=sorted(anchor_hits), kind='absent'))
        absent_pages.setdefault(d, set()).update(anchor_hits)

out = dict(
    loss_pages={d: sorted(s) for d, s in loss_pages.items()},
    absent_pages={d: sorted(s) for d, s in absent_pages.items()},
    name_pages=name_pages,
)
(CACHE / 'page_map.json').write_text(json.dumps(out, indent=1))
print('LOSS pages per doc:')
for d, s in sorted(loss_pages.items(), key=lambda x: -len(x[1])):
    npg = len(pagetext.get(d, []))
    print(f'  {len(s):2d}/{npg:3d} pages  {d}')
print('\nABSENT-family anchor pages per doc:')
for d, s in absent_pages.items():
    print(f'  {sorted(s)}  {d}')
# names with NO page located (loss names not found per-page)
noloc = [np for np in name_pages if np['kind'] == 'loss' and not np['pages']]
print(f'\nloss names with no per-page location: {len(noloc)} (of {sum(1 for x in name_pages if x["kind"]=="loss")})')

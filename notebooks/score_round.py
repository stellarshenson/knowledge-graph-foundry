import sys, json, re, collections, math
sys.path.insert(0, 'notebooks')
import warnings; warnings.filterwarnings('ignore')
from pathlib import Path
from parser_harness import *
import fitz  # pymupdf
from pypdf import PdfReader
import pdfplumber

docnames, rows = load_entities()
DOCSET = set(docnames)

# ---------- load parser full-doc texts ----------
trio = {p: load_text(p) for p in TRIO}
docling = load_text('docling')
tm = {p: norm_maps(trio[p]) for p in TRIO}
tm['docling'] = norm_maps(docling)

# ---------- map VLM combined outputs -> per (doc,page) then per-doc concat ----------
manifest = json.loads((CACHE / 'combined_manifest.json').read_text())
manifest2 = (json.loads((CACHE / 'combined_manifest2.json').read_text())
             if (CACHE / 'combined_manifest2.json').exists() else [])

def load_mineru_pages(dirname, stem):
    """page_idx -> text, via content_list.json of a combined run."""
    base = CACHE / dirname / stem / 'vlm'
    cl = base / f'{stem}_content_list.json'
    if not cl.exists():
        return None
    items = json.loads(cl.read_text())
    per = collections.defaultdict(list)
    for it in items:
        pi = it.get('page_idx')
        txt = it.get('text') or it.get('table_body') or it.get('html') or ''
        if isinstance(txt, str) and txt:
            per[pi].append(txt)
    return {pi: '\n'.join(v) for pi, v in per.items()}

def vlm_docmap(pagemap, man):
    """combined page_idx text -> {doc: concat}, {(doc,page): text}"""
    perdoc = collections.defaultdict(list); perpage = {}
    for idx, m in enumerate(man):
        t = pagemap.get(idx, '') if pagemap else ''
        perdoc[m['doc']].append(t)
        perpage[(m['doc'], m['page'])] = t
    return {d: '\n'.join(v) for d, v in perdoc.items()}, perpage

def load_mineru_chunks():
    """chunked rerun: chunk_XXX PDFs of chunk_size pages; global idx = chunk*size + page_idx."""
    cmap_p = CACHE / 'chunk_map.json'
    outdir = CACHE / 'mineru_chunks_out'
    if not cmap_p.exists() or not outdir.exists():
        return None, None
    cmap = json.loads(cmap_p.read_text())
    man_all = cmap['manifest_all']; ch = cmap['chunk_size']
    perdoc = collections.defaultdict(list); perpage = {}
    found = False
    for cd in sorted(outdir.iterdir()):
        stem = cd.name  # chunk_000
        cl = cd / 'vlm' / f'{stem}_content_list.json'
        if not cl.exists():
            continue
        found = True
        ci = int(stem.split('_')[1])
        per = collections.defaultdict(list)
        for it in json.loads(cl.read_text()):
            pi = it.get('page_idx')
            txt = it.get('text') or it.get('table_body') or it.get('html') or ''
            if isinstance(txt, str) and txt:
                per[pi].append(txt)
        for pi, parts in per.items():
            g = ci * ch + pi
            if g < len(man_all):
                m = man_all[g]
                t = '\n'.join(parts)
                perdoc[m['doc']].append(t)
                perpage[(m['doc'], m['page'])] = t
    if not found:
        return None, None
    return {d: '\n'.join(v) for d, v in perdoc.items()}, perpage

mineru_doc, mineru_pp = load_mineru_chunks()
if mineru_doc is None:
    mineru_pages = load_mineru_pages('mineru_combined', 'combined_vlm')
    mineru_doc, mineru_pp = vlm_docmap(mineru_pages, manifest) if mineru_pages else ({}, {})

def olm_natural(raw):
    """olmOCR-0225 emits JSON with a natural_text field; extract + unescape."""
    if not raw:
        return ''
    try:
        obj = json.loads(raw)
        nt = obj.get('natural_text')
        if isinstance(nt, str):
            return nt  # already real newlines after json.loads
    except Exception:
        pass
    # fallback: strip the front-matter wrapper, unescape \n
    return raw.replace('\\n', '\n')

def load_olm(which):
    perdoc = collections.defaultdict(list); perpage = {}
    for suffix in ('', '2'):
        p = CACHE / f'olmocr_{which}{suffix}.json'
        if not p.exists():
            continue
        d = json.loads(p.read_text())  # key 'doc||page'
        for k, t in d.items():
            doc, pg = k.rsplit('||', 1); pg = int(pg)
            nt = olm_natural(t)
            perdoc[doc].append(nt); perpage[(doc, pg)] = nt
    return {d2: '\n'.join(v) for d2, v in perdoc.items()}, perpage

olm_anc_doc, olm_anc_pp = load_olm('anchored')
olm_off_doc, olm_off_pp = load_olm('off')

# textmaps for doc-level presence
tm['mineru2.5'] = norm_maps(mineru_doc)
tm['olmocr_anchored'] = norm_maps(olm_anc_doc)
tm['olmocr_off'] = norm_maps(olm_off_doc)

ALLP = TRIO + ['docling', 'mineru2.5', 'olmocr_anchored', 'olmocr_off']

def found_any(name, docs, p):
    mp = tm.get(p, {})
    return any(present_in_doc(name, dn, mp) for dn in docs)

# ---------- reconstruct loss set (95) with credited docs ----------
parse_lost = []
for r in rows:
    fp = found_any(r['name'], r['docs'], 'pymupdf4llm')
    fa = found_any(r['name'], r['docs'], 'pdfplumber') or found_any(r['name'], r['docs'], 'pypdf')
    if (not fp) and fa:
        credit = [dn for dn in r['docs']
                  if not present_in_doc(r['name'], dn, tm['pymupdf4llm'])
                  and (present_in_doc(r['name'], dn, tm['pdfplumber']) or present_in_doc(r['name'], dn, tm['pypdf']))]
        parse_lost.append(dict(name=r['name'], credit=credit, docs=r['docs']))
LOSS = parse_lost
absent = [r for r in rows if not any(found_any(r['name'], r['docs'], p) for p in TRIO)]
ss_family = [r for r in absent if re.search(r'sleepstyle', r['name'], re.I)]

# ---------- recovery of loss set per parser (present in ANY credited doc) ----------
def loss_recovery(parser):
    hit = 0
    for pl in LOSS:
        docs = pl['credit'] or pl['docs']
        if any(present_in_doc(pl['name'], dn, tm.get(parser, {})) for dn in docs):
            hit += 1
    return hit, len(LOSS)

# ---------- overall named-string preservation per parser (all resolvable rows) ----------
def preservation(parser):
    return sum(found_any(r['name'], r['docs'], parser) for r in rows) / len(rows)

# ---------- H151 table-region partition (Docling TableFormer regions) ----------
dtab = json.loads((CACHE / 'docling_tabletext.json').read_text())
dtab_m = {d: (norm(t), nospace(t)) for d, t in dtab.items()}
def in_table_region(name, docs):
    return any((dn in dtab_m) and present_in(name, dtab_m[dn][0], dtab_m[dn][1]) for dn in docs)
for pl in LOSS:
    pl['table'] = in_table_region(pl['name'], pl['credit'] or pl['docs'])

# ---------- numeric floor (H148) ----------
NUMRE = re.compile(r'\d[\d.,]*\d|\d')
UNITRE = re.compile(r'^(cm|mm|kg|g|ml|l|oz|lb|hpa|db|dba|hz|w|v|a|min|h|hr|s|psi|bar|%|°c|c|f|years|year|months|month)$')
def num_tokens(text):
    return [m.group(0).strip('.,') for m in NUMRE.finditer(text or '')]
def num_contexts(text):
    """list of (number, ctxkey) using nearest preceding alpha word + following unit."""
    if not text: return []
    toks = re.findall(r"[A-Za-z%°]+|\d[\d.,]*\d|\d", text)
    out = []
    for i, t in enumerate(toks):
        if re.match(r'^\d', t):
            num = t.strip('.,')
            prev = next((toks[j].lower() for j in range(i-1, -1, -1) if re.match(r'[A-Za-z]', toks[j])), '')
            nxt = toks[i+1].lower() if i+1 < len(toks) and re.match(r'[A-Za-z%°]', toks[i+1]) else ''
            unit = nxt if UNITRE.match(nxt) else ''
            out.append((num, (prev[:12], unit)))
    return out

# per-page text for floor docs across text parsers (union reference)
nf = json.loads((CACHE / 'numeric_floor.json').read_text())
numeric_pages = {d: pgs for d, pgs in nf['numeric_pages'].items()}

def page_text_all_textparsers(doc, page):
    txts = []
    try:
        d = fitz.open(str(PDFDIR / doc))
        if page < d.page_count: txts.append(d[page].get_text())
        d.close()
    except Exception: pass
    try:
        rd = PdfReader(str(PDFDIR / doc))
        if page < len(rd.pages): txts.append(rd.pages[page].extract_text() or '')
    except Exception: pass
    try:
        with pdfplumber.open(str(PDFDIR / doc)) as pdf:
            if page < len(pdf.pages): txts.append(pdf.pages[page].extract_text() or '')
    except Exception: pass
    return txts  # list per parser

def score_numeric(vlm_pp, label):
    tot_ref = 0; rec = 0
    aligned = 0; exact = 0
    text_rec = 0; text_aligned = 0; text_exact = 0
    for doc, pages in numeric_pages.items():
        for pg in pages:
            key = (doc, pg)
            if vlm_pp and key not in vlm_pp:
                continue
            perparser = page_text_all_textparsers(doc, pg)
            ref_nums = set()
            for t in perparser: ref_nums |= set(num_tokens(t))
            ref_ctx = {}
            for t in perparser:
                for num, ck in num_contexts(t): ref_ctx[ck] = num
            if not ref_nums: continue
            tot_ref += len(ref_nums)
            vt = vlm_pp.get(key, '') if vlm_pp else ''
            vlm_nums = set(num_tokens(vt))
            rec += len(ref_nums & vlm_nums)
            # digit precision: context-aligned
            for num, ck in num_contexts(vt):
                if ck in ref_ctx and ck[0]:
                    aligned += 1
                    if num == ref_ctx[ck]: exact += 1
            # text-parser baseline (use pypdf as representative text parser = perparser[-2] if exists)
            base = perparser[1] if len(perparser) > 1 else (perparser[0] if perparser else '')
            base_nums = set(num_tokens(base))
            text_rec += len(ref_nums & base_nums)
            for num, ck in num_contexts(base):
                if ck in ref_ctx and ck[0]:
                    text_aligned += 1
                    if num == ref_ctx[ck]: text_exact += 1
    return dict(label=label, ref=tot_ref, recall=rec/tot_ref if tot_ref else None,
                digit_precision=exact/aligned if aligned else None, aligned=aligned,
                text_recall=text_rec/tot_ref if tot_ref else None,
                text_digit_precision=text_exact/text_aligned if text_aligned else None)

# ---------- absent family precision (hallucination candidates) ----------
def sleepstyle_strings(text):
    return set(m.group(0).strip() for m in re.finditer(r'SleepStyle[\w\s\-&/]{0,40}', text or '', re.I))

# ---------- symbol-stripped matching variant (™/®/© are matching artifacts) ----------
SYM = re.compile(r'[™®©]')
def norm2(x): return norm(SYM.sub(' ', x or ''))
def nospace2(x): return nospace(SYM.sub('', x or ''))
def maps2(td): return {d: (norm2(t), nospace2(t)) for d, t in td.items()}
def present2(name, dn, mp):
    if dn not in mp: return False
    tn, ts = mp[dn]
    nn = norm2(name)
    if nn and nn in tn: return True
    ns = nospace2(name)
    return bool(ns) and ns in ts

tm2 = {p: maps2(trio[p]) for p in TRIO}
tm2['docling'] = maps2(docling)
tm2['mineru2.5'] = maps2(mineru_doc or {})
tm2['olmocr_anchored'] = maps2(olm_anc_doc)
tm2['olmocr_off'] = maps2(olm_off_doc)

# ---------- H147 absent-family recovery + precision (SleepStyle mode-family) ----------
KNOWN_SS = [r['name'] for r in ss_family]
def absent_family_recovery(parser_pp, parser_doc_tm):
    """recovery of the 7 known SleepStyle names; precision via hallucination candidates."""
    recovered = []
    for r in ss_family:
        docs = r['docs']
        if any(present_in_doc(r['name'], dn, parser_doc_tm) for dn in docs):
            recovered.append(r['name'])
    # hallucination candidates: SleepStyle-prefixed strings the parser emits that are NOT known
    emitted = set()
    for (doc, pg), txt in (parser_pp or {}).items():
        emitted |= sleepstyle_strings(txt)
    known_norm = {norm(k) for k in KNOWN_SS} | {norm('Fisher & Paykel SleepStyle'), norm('SleepStyle')}
    novel = sorted({s for s in emitted if norm(s) not in known_norm
                    and not any(norm(s) in norm(k) or norm(k) in norm(s) for k in KNOWN_SS)})
    n_rec = len(recovered)
    n_emit_known = n_rec  # matched known
    precision = n_emit_known / (n_emit_known + len(novel)) if (n_emit_known + len(novel)) else None
    return dict(recovered=recovered, n_recovered=n_rec, n_family=len(ss_family),
                recall=n_rec/len(ss_family) if ss_family else None,
                hallucination_candidates=novel, name_precision=precision)

# ---------- H149 olmOCR anchored vs off: loss-name recovery ----------
def olm_loss_recovery(which_tm):
    h = 0
    for pl in LOSS:
        docs = pl['credit'] or pl['docs']
        if any(present_in_doc(pl['name'], dn, which_tm) for dn in docs):
            h += 1
    return h, len(LOSS)

# ---------- H151 group recovery on table-region subset ----------
def group_recovery_table(parsers):
    tabloss = [pl for pl in LOSS if pl['table']]
    nontab = [pl for pl in LOSS if not pl['table']]
    def grp(subset):
        # union recovery: recovered if ANY parser in group finds it
        rec = 0
        for pl in subset:
            docs = pl['credit'] or pl['docs']
            if any(any(present_in_doc(pl['name'], dn, tm.get(p, {})) for dn in docs) for p in parsers):
                rec += 1
        return rec, len(subset)
    # also mean of individual recoveries
    def mean_indiv(subset):
        vals = []
        for p in parsers:
            r = sum(1 for pl in subset
                    if any(present_in_doc(pl['name'], dn, tm.get(p, {})) for dn in (pl['credit'] or pl['docs'])))
            vals.append(r/len(subset) if subset else 0)
        return sum(vals)/len(vals) if vals else 0
    return dict(table_union=grp(tabloss), nontab_union=grp(nontab),
                table_mean=mean_indiv(tabloss), nontab_mean=mean_indiv(nontab))

def spearman(a, b):
    n = len(a)
    def rank(x):
        order = sorted(range(n), key=lambda i: x[i])
        r = [0]*n
        i = 0
        while i < n:
            j = i
            while j+1 < n and x[order[j+1]] == x[order[i]]: j += 1
            avg = (i+j)/2 + 1
            for k in range(i, j+1): r[order[k]] = avg
            i = j+1
        return r
    ra, rb = rank(a), rank(b)
    dbar_a = sum(ra)/n; dbar_b = sum(rb)/n
    cov = sum((ra[i]-dbar_a)*(rb[i]-dbar_b) for i in range(n))
    va = math.sqrt(sum((ra[i]-dbar_a)**2 for i in range(n)))
    vb = math.sqrt(sum((rb[i]-dbar_b)**2 for i in range(n)))
    return cov/(va*vb) if va*vb else None

if __name__ == '__main__':
    import datetime
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
    have_mineru = bool(tm.get('mineru2.5'))
    have_olm = bool(tm.get('olmocr_anchored'))
    print('=== loss set / absent reconstructed ===')
    ntab = sum(1 for pl in LOSS if pl['table'])
    print('LOSS', len(LOSS), 'absent-all', len(absent), 'ss_family', len(ss_family))
    print(f'table-region losses: {ntab}/{len(LOSS)} = {ntab/len(LOSS):.1%}')
    print('\n=== per-parser loss-set recovery + preservation ===')
    recall_by_parser = {}
    for p in ALLP:
        if p in ('mineru2.5','olmocr_anchored','olmocr_off') and not tm.get(p):
            print(f'  {p:18s} (no output yet)'); continue
        h, n = loss_recovery(p)
        recall_by_parser[p] = h/n
        print(f'  {p:18s} loss-recovery {h:3d}/{n} = {h/n:.1%}   preservation {preservation(p):.1%}')

    runtimes = {}
    for rf, key in [('docling_runtime.json','docling'), ('olmocr_runtime.json','olmocr'), ('mineru_runtime.json','mineru')]:
        p = CACHE/rf
        if p.exists():
            v = json.loads(p.read_text()); runtimes[key] = round(sum(v.values())/len(v),1) if v else None

    # ---- H146 ----
    dh, dn = loss_recovery('docling')
    h146 = dict(hypothesis='R14-H146', parser='docling(docling-parse,CPU,OCR-off)',
        loss_set_recovery=dh/dn, loss_set_hits=dh, loss_set_n=dn, bar=0.60,
        union_baseline_preservation=0.7583988563259471, docling_preservation=preservation('docling'),
        pymupdf4llm_recovery=loss_recovery('pymupdf4llm')[0]/dn,
        verdict='CONFIRMED' if dh/dn>=0.60 else 'REFUTED',
        runtime_s_per_page=runtimes.get('docling'))
    json.dump(h146, open(f'reports/experiments/adjudicated/parser-h146-docling-{stamp}.json','w'), indent=2)

    # ---- H147 ----
    if have_mineru:
        af = absent_family_recovery(mineru_pp, tm['mineru2.5'])
        # dual matching: strict H51 vs symbol-stripped (the artifact discovery)
        fam_table = {}
        for p in ['pymupdf4llm','pdfplumber','pypdf','docling','mineru2.5','olmocr_anchored','olmocr_off']:
            strict = sum(1 for r in ss_family if any(present_in_doc(r['name'], dn, tm.get(p, {})) for dn in r['docs']))
            loose = sum(1 for r in ss_family if any(present2(r['name'], dn, tm2.get(p, {})) for dn in r['docs']))
            fam_table[p] = dict(strict=strict, sym_stripped=loose, n=len(ss_family))
        # how much of the 676 absent set does sym-stripping alone rescue (trio union)
        rescued = [r['name'] for r in absent
                   if any(any(present2(r['name'], dn, tm2[p]) for dn in r['docs']) for p in TRIO)]
        mineru_loose = fam_table['mineru2.5']['sym_stripped'] / len(ss_family)
        h147 = dict(hypothesis='R14-H147', parser='MinerU2.5-1.2B(vlm-engine,GPU0)',
            **af, bar_recall=0.50, bar_precision=0.90, known_family=KNOWN_SS,
            family_recovery_matrix=fam_table,
            mineru_family_recall_sym_stripped=mineru_loose,
            absent_set_rescued_by_sym_strip=len(rescued),
            absent_set_total=len(absent),
            artifact_finding=('The all-parser-absent SleepStyle family is a matching ARTIFACT: every text parser '
                              'emits the names with an interposed trademark glyph (SleepStyle(TM) Auto); H51 exact '
                              'normalization fails on the glyph. pypdf and docling recover 7/7 under sym-stripped '
                              'matching - the class is not rendered-but-unencoded text. 69/676 of the whole absent '
                              'set is rescued by sym-stripping alone.'),
            verdict='REFUTED (premise falsified: family is a normalization artifact, vision not necessary)')
        json.dump(h147, open(f'reports/experiments/adjudicated/parser-h147-mineru-absent-{stamp}.json','w'), indent=2)
        print('\nH147 family matrix:', fam_table)
        print('H147 rescued from absent set by sym-strip:', len(rescued), '/', len(absent))

    # ---- H148 ----
    if have_mineru:
        num_mineru = score_numeric(mineru_pp, 'mineru2.5')
        num_olm = score_numeric(olm_off_pp, 'olmocr_off') if have_olm else None
        # the true floor residue: 16 (gold,src) pairs failed by ALL text parsers - can any VLM emit them?
        failed = json.loads((CACHE / 'failed_gold_checks.json').read_text())
        def digitsonly(x): return re.sub(r'[^0-9a-z.]', '', (x or '').lower())
        def vlm_has(gold, doc, docmap_tm, docmap2, rawdoc):
            if present_in_doc(gold, doc, docmap_tm): return 'strict'
            if present2(gold, doc, docmap2): return 'sym'
            if doc in rawdoc and digitsonly(gold) and digitsonly(gold) in digitsonly(rawdoc[doc]): return 'digits'
            return None
        floor_results = []
        for fc in failed:
            row = dict(fc)
            row['mineru'] = vlm_has(fc['gold'], fc['src'], tm['mineru2.5'], tm2['mineru2.5'], mineru_doc or {})
            row['olmocr_off'] = vlm_has(fc['gold'], fc['src'], tm['olmocr_off'], tm2['olmocr_off'], olm_off_doc)
            row['olmocr_anchored'] = vlm_has(fc['gold'], fc['src'], tm['olmocr_anchored'], tm2['olmocr_anchored'], olm_anc_doc)
            floor_results.append(row)
        n_mineru_lift = sum(1 for r in floor_results if r['mineru'])
        n_olm_lift = sum(1 for r in floor_results if r['olmocr_off'])
        h148 = dict(hypothesis='R14-H148', mineru=num_mineru, olmocr_off=num_olm,
            bar='recall >= text+0.10 AND digit_precision >= text baseline',
            recall_gain=(num_mineru['recall'] or 0)-(num_mineru['text_recall'] or 0),
            floor_residue_n=len(floor_results),
            floor_residue_vlm_lift=dict(mineru=n_mineru_lift, olmocr_off=n_olm_lift),
            floor_residue_detail=floor_results,
            floor_note=('16 (gold,src) pairs failed by ALL text parsers are cross-product pairings of probe '
                        'evidence x sources; VLM coverage = spec/gold pages included in combined PDF only'),
            verdict=('CONFIRMED' if (num_mineru['recall'] or 0) >= (num_mineru['text_recall'] or 0)+0.10
                     and (num_mineru['digit_precision'] or 0) >= (num_mineru['text_digit_precision'] or 0)
                     else 'REFUTED'))
        json.dump(h148, open(f'reports/experiments/adjudicated/parser-h148-numeric-{stamp}.json','w'), indent=2)
        print('\nH148 mineru', num_mineru)
        print('H148 floor residue lifted: mineru', n_mineru_lift, '/16, olmocr_off', n_olm_lift, '/16')

    # ---- H149 ----
    if have_olm:
        ah, an = olm_loss_recovery(tm['olmocr_anchored'])
        oh, on = olm_loss_recovery(tm['olmocr_off'])
        pym_lost_n = len(LOSS)
        h149 = dict(hypothesis='R14-H149', parser='olmOCR-7B-0225-preview(GPU2,bf16)',
            anchored_recovery=ah/an, anchor_off_recovery=oh/on,
            anchored_hits=ah, anchor_off_hits=oh, n=an,
            clause1_anchored_ge_half=ah/an>=0.50, clause2_off_gt_anchored=oh>ah,
            note='anchor-off = empty RAW_TEXT block (image-only signal); anchored = real pypdf anchor via olmocr.get_anchor_text',
            verdict=('CONFIRMED' if ah/an>=0.50 and oh>ah else 'REFUTED'))
        json.dump(h149, open(f'reports/experiments/adjudicated/parser-h149-olmocr-anchor-{stamp}.json','w'), indent=2)
        print('\nH149 anchored', f'{ah}/{an}={ah/an:.1%}', 'off', f'{oh}/{on}={oh/on:.1%}')

    # ---- H150 ----
    # Benchmark numbers used (registered): MinerU2.5 90.67 (OmniDocBench overall), MinerU-classic
    # pipeline 79.4 EN table-TEDS used as the Docling/TableFormer pipeline-class proxy (digest:
    # docling competitive among pipeline tools, below MinerU on tables), olmOCR-2 82.4 (olmOCR-bench
    # proxy, same model both anchor configs). H51 trio: bare text extractors, NO table-structure
    # stage, no OmniDocBench entry - table-TEDS assigned 0 (stated assumption; registration demands
    # they be included). dots.ocr 88.6 and Marker 54.0 not run here, excluded.
    teds_used = {'pymupdf4llm': 0.0, 'pdfplumber': 0.0, 'pypdf': 0.0,
                 'docling': 79.4, 'mineru2.5': 90.67,
                 'olmocr_anchored': 82.4, 'olmocr_off': 82.4}
    parsers_for_corr = [p for p in teds_used if p in recall_by_parser]
    if have_mineru and have_olm:
        xs = [teds_used[p] for p in parsers_for_corr]
        ys = [recall_by_parser[p] for p in parsers_for_corr]
        rho = spearman(xs, ys)
        sub = [p for p in parsers_for_corr if p not in TRIO]
        rho_bench = spearman([teds_used[p] for p in sub], [recall_by_parser[p] for p in sub]) if len(sub) >= 3 else None
        h150 = dict(hypothesis='R14-H150', parsers=parsers_for_corr,
            teds=xs, name_recall_loss_set=ys, spearman=rho,
            spearman_bench_only=rho_bench, bench_only_parsers=sub,
            bar='<0.5 confirms; >=0.8 refutes',
            teds_source=('MinerU2.5 90.67 OmniDocBench overall; Docling assigned 79.4 (MinerU-classic pipeline EN '
                         'table-TEDS as pipeline-class proxy); olmOCR-2 82.4 olmOCR-bench proxy; H51 trio assigned 0 '
                         '(no table-structure stage). dots.ocr 88.6 / Marker 54.0 not run, excluded.'),
            verdict=('CONFIRMED' if rho is not None and rho<0.5 else ('REFUTED' if rho is not None and rho>=0.8 else 'INCONCLUSIVE')))
        json.dump(h150, open(f'reports/experiments/adjudicated/parser-h150-teds-corr-{stamp}.json','w'), indent=2)
        print('\nH150 spearman', rho, '(bench-only', rho_bench, ') over', parsers_for_corr)

    # ---- H151 ----
    with_grp = ['docling'] + (['mineru2.5'] if have_mineru else [])
    without_grp = ['pymupdf4llm','pypdf','pdfplumber']
    gr_with = group_recovery_table(with_grp)
    gr_without = group_recovery_table(without_grp)
    h151 = dict(hypothesis='R14-H151',
        table_region_frac=ntab/len(LOSS), bar_a=0.70,
        with_table_stage=with_grp, without_table_stage=without_grp,
        with_group=gr_with, without_group=gr_without,
        clause_a=ntab/len(LOSS)>=0.70,
        ratio_union=(gr_with['table_union'][0]/max(gr_without['table_union'][0],1)),
        ratio_mean=(gr_with['table_mean']/gr_without['table_mean'] if gr_without['table_mean'] else None),
        caveat='loss set is DEFINED as names pypdf/pdfplumber recover but pymupdf4llm drops; the without-table-stage group thus recovers it near-fully by construction (pypdf alone %.1f%%)' % (100*recall_by_parser.get('pypdf',0)),
        verdict='see report')
    json.dump(h151, open(f'reports/experiments/adjudicated/parser-h151-table-partition-{stamp}.json','w'), indent=2)
    print('\nH151 table_frac', f'{ntab/len(LOSS):.1%}', 'with', gr_with, 'without', gr_without)
    print('\nstamp', stamp)
